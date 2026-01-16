# MAST Benchmark Report

**Generated:** 2026-01-16 16:13:06 UTC
**Run ID:** 747a5b90
**Duration:** 51.8 seconds

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Records | 1,242 |
| Processed | 1,242 |
| Detections | 3,402 |
| Macro F1 | 0.634 |
| Micro F1 | 0.765 |
| Weighted F1 | 0.763 |
| Overall Accuracy | 89.8% |
| ECE (Calibration) | 0.537 |
| Mean Latency | 2.5 ms/record |

## Per-Failure-Mode Results

### High Performance (F1 >= 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F11 | Coordination Failure | 0.831 | 0.982 | 0.900 | 0.883 | 110 |
| F14 | Completion Misjudgment | 0.917 | 0.733 | 0.815 | 0.927 | 45 |

### Medium Performance (0.50 <= F1 < 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F1 | Specification Mismatch | 0.610 | 0.924 | 0.735 | 0.786 | 66 |
| F12 | Output Validation Failure | 0.774 | 0.480 | 0.593 | 0.840 | 50 |
| F13 | Quality Gate Bypass | 0.861 | 0.738 | 0.795 | 0.922 | 42 |
| F3 | Resource Misallocation | 0.909 | 0.682 | 0.779 | 0.835 | 88 |
| F4 | Inadequate Tool Provision | 0.923 | 0.545 | 0.686 | 0.947 | 22 |
| F5 | Flawed Workflow Design | 0.922 | 0.701 | 0.797 | 0.883 | 67 |
| F6 | Task Derailment | 0.692 | 0.600 | 0.643 | 0.951 | 15 |
| F7 | Context Neglect | 0.543 | 0.905 | 0.679 | 0.738 | 63 |
| F8 | Information Withholding | 0.882 | 0.588 | 0.706 | 0.879 | 51 |
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
Actual Pos     61      5  (TP, FN)
       Neg     39    101  (FP, TN)
```

### F11: Coordination Failure

```
              Predicted
            Pos    Neg
Actual Pos    108      2  (TP, FN)
       Neg     22     74  (FP, TN)
```

### F12: Output Validation Failure

```
              Predicted
            Pos    Neg
Actual Pos     24     26  (TP, FN)
       Neg      7    149  (FP, TN)
```

### F13: Quality Gate Bypass

```
              Predicted
            Pos    Neg
Actual Pos     31     11  (TP, FN)
       Neg      5    159  (FP, TN)
```

### F14: Completion Misjudgment

```
              Predicted
            Pos    Neg
Actual Pos     33     12  (TP, FN)
       Neg      3    158  (FP, TN)
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
Actual Pos     60     28  (TP, FN)
       Neg      6    112  (FP, TN)
```

### F4: Inadequate Tool Provision

```
              Predicted
            Pos    Neg
Actual Pos     12     10  (TP, FN)
       Neg      1    183  (FP, TN)
```

### F5: Flawed Workflow Design

```
              Predicted
            Pos    Neg
Actual Pos     47     20  (TP, FN)
       Neg      4    135  (FP, TN)
```

### F6: Task Derailment

```
              Predicted
            Pos    Neg
Actual Pos      9      6  (TP, FN)
       Neg      4    187  (FP, TN)
```

### F7: Context Neglect

```
              Predicted
            Pos    Neg
Actual Pos     57      6  (TP, FN)
       Neg     48     95  (FP, TN)
```

### F8: Information Withholding

```
              Predicted
            Pos    Neg
Actual Pos     30     21  (TP, FN)
       Neg      4    151  (FP, TN)
```

### F9: Role Usurpation

```
              Predicted
            Pos    Neg
Actual Pos      6      4  (TP, FN)
       Neg      0    196  (FP, TN)
```
