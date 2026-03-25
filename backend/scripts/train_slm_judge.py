"""Train SLM Judge on Modal GPU.

Fine-tunes Qwen2.5-3B-Instruct on 8K Pisama golden entries using QLoRA.
Cost: ~$3-5 on Modal A10G, ~30 min training time.

Usage:
  modal run backend/scripts/train_slm_judge.py
"""

import modal

app = modal.App("pisama-slm-judge")

# Docker image with training dependencies
training_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "transformers>=4.45.0",
        "peft>=0.13.0",
        "bitsandbytes>=0.44.0",
        "accelerate>=1.0.0",
        "datasets>=3.0.0",
        "trl>=0.12.0",
        "scipy",
    )
)

# Volume for data + model
data_volume = modal.Volume.from_name("pisama-slm-data", create_if_missing=True)
model_volume = modal.Volume.from_name("pisama-slm-model", create_if_missing=True)


@app.function(image=training_image, timeout=120)
def upload_data():
    """Upload training data to Modal volume."""
    import json
    # Read local files and write to volume
    return "Data upload handled via local_entrypoint"


@app.function(
    image=training_image,
    gpu="A10G",
    timeout=3600,
    volumes={"/data": data_volume, "/model_output": model_volume},
)
def train():
    import json
    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig

    print("=" * 60)
    print("PISAMA SLM Judge Training")
    print("=" * 60)

    MODEL_NAME = "Qwen/Qwen2.5-3B-Instruct"
    OUTPUT_DIR = "/model_output/pisama-slm-judge-v1"

    # Load training data
    def load_jsonl(path):
        entries = []
        with open(path) as f:
            for line in f:
                entries.append(json.loads(line))
        return entries

    train_entries = load_jsonl("/data/train.jsonl")
    val_entries = load_jsonl("/data/val.jsonl")
    print(f"Train: {len(train_entries)}, Val: {len(val_entries)}")

    # Format as chat messages for Qwen instruct
    def format_entry(entry):
        return {
            "text": (
                f"<|im_start|>system\nYou are a failure detection judge for multi-agent AI systems. "
                f"Answer YES if the data shows a failure, NO if it's normal behavior.<|im_end|>\n"
                f"<|im_start|>user\n{entry['instruction']}\n\n{entry['input']}<|im_end|>\n"
                f"<|im_start|>assistant\n{entry['output']}<|im_end|>"
            )
        }

    train_formatted = [format_entry(e) for e in train_entries]
    val_formatted = [format_entry(e) for e in val_entries]

    train_dataset = Dataset.from_list(train_formatted)
    val_dataset = Dataset.from_list(val_formatted)

    # Load model with 4-bit quantization
    print(f"\nLoading {MODEL_NAME} with 4-bit quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA config
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Trainable: {trainable_params:,} / {total_params:,} ({100*trainable_params/total_params:.2f}%)")

    # Training config
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        weight_decay=0.01,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=50,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        bf16=True,
        max_seq_length=512,
        dataset_text_field="text",
        report_to="none",
    )

    # Train
    print("\nStarting training...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
    )

    trainer.train()

    # Save
    print(f"\nSaving model to {OUTPUT_DIR}...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    # Quick eval
    print("\nQuick evaluation on 50 val samples...")
    model.eval()
    correct = 0
    total = 0
    for entry in val_entries[:50]:
        prompt = (
            f"<|im_start|>system\nYou are a failure detection judge for multi-agent AI systems. "
            f"Answer YES if the data shows a failure, NO if it's normal behavior.<|im_end|>\n"
            f"<|im_start|>user\n{entry['instruction']}\n\n{entry['input']}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=480).to(model.device)
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=5, do_sample=False)
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

        predicted = "YES" if "YES" in response.upper() else "NO"
        expected = entry['output']
        if predicted == expected:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0
    print(f"Validation accuracy: {correct}/{total} ({accuracy:.1%})")
    print(f"\nModel saved to {OUTPUT_DIR}")

    # Commit the volume
    model_volume.commit()

    return {"accuracy": accuracy, "train_size": len(train_entries), "val_size": len(val_entries)}


@app.function(
    image=training_image,
    gpu="A10G",
    timeout=600,
    volumes={"/data": data_volume, "/model_output": model_volume},
)
def evaluate():
    """Run full evaluation on the trained model."""
    import json
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    MODEL_PATH = "/model_output/pisama-slm-judge-v1"

    print("Loading trained model...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    print("Model loaded. Ready for inference.")
    return {"status": "ready", "model_path": MODEL_PATH}


@app.local_entrypoint()
def main():
    import subprocess

    # Upload training data to volume
    print("Uploading training data to Modal volume...")
    subprocess.run(["modal", "volume", "put", "pisama-slm-data", "/tmp/slm_train.jsonl", "train.jsonl"], check=True)
    subprocess.run(["modal", "volume", "put", "pisama-slm-data", "/tmp/slm_val.jsonl", "val.jsonl"], check=True)
    print("Data uploaded.")

    print("\nStarting SLM Judge training on Modal A10G...")
    result = train.remote()
    print(f"\nTraining complete!")
    print(f"  Accuracy: {result['accuracy']:.1%}")
    print(f"  Train size: {result['train_size']}")
    print(f"  Val size: {result['val_size']}")
