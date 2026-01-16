# MAST Benchmark Report

**Generated:** 2026-01-16 08:27:13 UTC
**Run ID:** 85c5cda3
**Duration:** 1.6 seconds

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Records | 1,242 |
| Processed | 1,242 |
| Detections | 1,343 |
| Macro F1 | 0.100 |
| Micro F1 | 0.223 |
| Weighted F1 | 0.168 |
| Overall Accuracy | 74.3% |
| ECE (Calibration) | 0.270 |
| Mean Latency | 0.0 ms/record |

## Per-Failure-Mode Results

### Low Performance (F1 < 0.50)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F1 | Specification Mismatch | 0.476 | 0.152 | 0.230 | 0.675 | 66 |
| F10 | Communication Breakdown | 0.000 | 0.000 | 0.000 | 0.981 | 0 |
| F11 | Coordination Failure | 0.600 | 0.055 | 0.100 | 0.476 | 110 |
| F12 | Output Validation Failure | 0.270 | 0.340 | 0.301 | 0.617 | 50 |
| F13 | Quality Gate Bypass | 0.222 | 0.048 | 0.078 | 0.772 | 42 |
| F14 | Completion Misjudgment | 0.212 | 0.778 | 0.333 | 0.320 | 45 |
| F15 | Grounding Failure | 0.000 | 0.000 | 0.000 | 1.000 | 0 |
| F16 | Retrieval Quality Failure | 0.000 | 0.000 | 0.000 | 1.000 | 0 |
| F2 | Poor Task Decomposition | 0.000 | 0.000 | 0.000 | 0.806 | 3 |
| F3 | Resource Misallocation | 0.384 | 0.545 | 0.451 | 0.432 | 88 |
| F4 | Inadequate Tool Provision | 0.000 | 0.000 | 0.000 | 0.869 | 22 |
| F5 | Flawed Workflow Design | 0.231 | 0.045 | 0.075 | 0.641 | 67 |
| F6 | Task Derailment | 0.000 | 0.000 | 0.000 | 0.927 | 15 |
| F7 | Context Neglect | 0.125 | 0.016 | 0.028 | 0.665 | 63 |
| F8 | Information Withholding | 0.000 | 0.000 | 0.000 | 0.752 | 51 |
| F9 | Role Usurpation | 0.000 | 0.000 | 0.000 | 0.951 | 10 |

## Confusion Matrices

### F1: Specification Mismatch

```
              Predicted
            Pos    Neg
Actual Pos     10     56  (TP, FN)
       Neg     11    129  (FP, TN)
```

### F10: Communication Breakdown

```
              Predicted
            Pos    Neg
Actual Pos      0      0  (TP, FN)
       Neg      4    202  (FP, TN)
```

### F11: Coordination Failure

```
              Predicted
            Pos    Neg
Actual Pos      6    104  (TP, FN)
       Neg      4     92  (FP, TN)
```

### F12: Output Validation Failure

```
              Predicted
            Pos    Neg
Actual Pos     17     33  (TP, FN)
       Neg     46    110  (FP, TN)
```

### F13: Quality Gate Bypass

```
              Predicted
            Pos    Neg
Actual Pos      2     40  (TP, FN)
       Neg      7    157  (FP, TN)
```

### F14: Completion Misjudgment

```
              Predicted
            Pos    Neg
Actual Pos     35     10  (TP, FN)
       Neg    130     31  (FP, TN)
```

### F15: Grounding Failure

```
              Predicted
            Pos    Neg
Actual Pos      0      0  (TP, FN)
       Neg      0    206  (FP, TN)
```

### F16: Retrieval Quality Failure

```
              Predicted
            Pos    Neg
Actual Pos      0      0  (TP, FN)
       Neg      0    206  (FP, TN)
```

### F2: Poor Task Decomposition

```
              Predicted
            Pos    Neg
Actual Pos      0      3  (TP, FN)
       Neg     37    166  (FP, TN)
```

### F3: Resource Misallocation

```
              Predicted
            Pos    Neg
Actual Pos     48     40  (TP, FN)
       Neg     77     41  (FP, TN)
```

### F4: Inadequate Tool Provision

```
              Predicted
            Pos    Neg
Actual Pos      0     22  (TP, FN)
       Neg      5    179  (FP, TN)
```

### F5: Flawed Workflow Design

```
              Predicted
            Pos    Neg
Actual Pos      3     64  (TP, FN)
       Neg     10    129  (FP, TN)
```

### F6: Task Derailment

```
              Predicted
            Pos    Neg
Actual Pos      0     15  (TP, FN)
       Neg      0    191  (FP, TN)
```

### F7: Context Neglect

```
              Predicted
            Pos    Neg
Actual Pos      1     62  (TP, FN)
       Neg      7    136  (FP, TN)
```

### F8: Information Withholding

```
              Predicted
            Pos    Neg
Actual Pos      0     51  (TP, FN)
       Neg      0    155  (FP, TN)
```

### F9: Role Usurpation

```
              Predicted
            Pos    Neg
Actual Pos      0     10  (TP, FN)
       Neg      0    196  (FP, TN)
```
