# MAST Benchmark Report

**Generated:** 2026-01-16 16:22:35 UTC
**Run ID:** 9c5f5548
**Duration:** 50.7 seconds

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Records | 1,242 |
| Processed | 1,242 |
| Detections | 4,231 |
| Macro F1 | 0.640 |
| Micro F1 | 0.747 |
| Weighted F1 | 0.761 |
| Overall Accuracy | 87.1% |
| ECE (Calibration) | 0.528 |
| Mean Latency | 2.4 ms/record |

## Per-Failure-Mode Results

### High Performance (F1 >= 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F11 | Coordination Failure | 0.838 | 0.991 | 0.908 | 0.893 | 110 |
| F13 | Quality Gate Bypass | 0.912 | 0.738 | 0.816 | 0.932 | 42 |
| F14 | Completion Misjudgment | 0.943 | 0.733 | 0.825 | 0.932 | 45 |
| F5 | Flawed Workflow Design | 1.000 | 0.701 | 0.825 | 0.903 | 67 |

### Medium Performance (0.50 <= F1 < 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F1 | Specification Mismatch | 0.620 | 0.939 | 0.747 | 0.796 | 66 |
| F12 | Output Validation Failure | 0.462 | 0.960 | 0.623 | 0.718 | 50 |
| F3 | Resource Misallocation | 0.571 | 0.955 | 0.715 | 0.675 | 88 |
| F4 | Inadequate Tool Provision | 1.000 | 0.545 | 0.706 | 0.951 | 22 |
| F6 | Task Derailment | 1.000 | 0.600 | 0.750 | 0.971 | 15 |
| F7 | Context Neglect | 0.541 | 0.937 | 0.686 | 0.738 | 63 |
| F8 | Information Withholding | 0.457 | 0.941 | 0.615 | 0.709 | 51 |
| F9 | Role Usurpation | 1.000 | 0.600 | 0.750 | 0.981 | 10 |

### Low Performance (F1 < 0.50)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F15 | Grounding Failure | 0.000 | 0.000 | 0.000 | 1.000 | 0 |
| F16 | Retrieval Quality Failure | 0.000 | 0.000 | 0.000 | 1.000 | 0 |

## Confusion Matrices

### F1: Specification Mismatch

```
              Predicted
            Pos    Neg
Actual Pos     62      4  (TP, FN)
       Neg     38    102  (FP, TN)
```

### F11: Coordination Failure

```
              Predicted
            Pos    Neg
Actual Pos    109      1  (TP, FN)
       Neg     21     75  (FP, TN)
```

### F12: Output Validation Failure

```
              Predicted
            Pos    Neg
Actual Pos     48      2  (TP, FN)
       Neg     56    100  (FP, TN)
```

### F13: Quality Gate Bypass

```
              Predicted
            Pos    Neg
Actual Pos     31     11  (TP, FN)
       Neg      3    161  (FP, TN)
```

### F14: Completion Misjudgment

```
              Predicted
            Pos    Neg
Actual Pos     33     12  (TP, FN)
       Neg      2    159  (FP, TN)
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

### F3: Resource Misallocation

```
              Predicted
            Pos    Neg
Actual Pos     84      4  (TP, FN)
       Neg     63     55  (FP, TN)
```

### F4: Inadequate Tool Provision

```
              Predicted
            Pos    Neg
Actual Pos     12     10  (TP, FN)
       Neg      0    184  (FP, TN)
```

### F5: Flawed Workflow Design

```
              Predicted
            Pos    Neg
Actual Pos     47     20  (TP, FN)
       Neg      0    139  (FP, TN)
```

### F6: Task Derailment

```
              Predicted
            Pos    Neg
Actual Pos      9      6  (TP, FN)
       Neg      0    191  (FP, TN)
```

### F7: Context Neglect

```
              Predicted
            Pos    Neg
Actual Pos     59      4  (TP, FN)
       Neg     50     93  (FP, TN)
```

### F8: Information Withholding

```
              Predicted
            Pos    Neg
Actual Pos     48      3  (TP, FN)
       Neg     57     98  (FP, TN)
```

### F9: Role Usurpation

```
              Predicted
            Pos    Neg
Actual Pos      6      4  (TP, FN)
       Neg      0    196  (FP, TN)
```
