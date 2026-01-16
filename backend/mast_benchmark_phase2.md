# MAST Benchmark Report

**Generated:** 2026-01-16 17:58:28 UTC
**Run ID:** 08bff0c6
**Duration:** 50.2 seconds

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Records | 1,242 |
| Processed | 1,242 |
| Detections | 5,163 |
| Macro F1 | 0.585 |
| Micro F1 | 0.681 |
| Weighted F1 | 0.692 |
| Overall Accuracy | 82.0% |
| ECE (Calibration) | 0.500 |
| Mean Latency | 2.4 ms/record |

## Per-Failure-Mode Results

### High Performance (F1 >= 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F11 | Coordination Failure | 0.697 | 0.982 | 0.815 | 0.762 | 110 |
| F13 | Quality Gate Bypass | 0.909 | 0.714 | 0.800 | 0.927 | 42 |

### Medium Performance (0.50 <= F1 < 0.80)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F1 | Specification Mismatch | 0.504 | 0.985 | 0.667 | 0.684 | 66 |
| F12 | Output Validation Failure | 0.443 | 0.940 | 0.603 | 0.699 | 50 |
| F14 | Completion Misjudgment | 0.371 | 0.956 | 0.534 | 0.636 | 45 |
| F3 | Resource Misallocation | 0.583 | 0.920 | 0.714 | 0.684 | 88 |
| F4 | Inadequate Tool Provision | 0.923 | 0.545 | 0.686 | 0.947 | 22 |
| F5 | Flawed Workflow Design | 0.517 | 0.910 | 0.659 | 0.694 | 67 |
| F6 | Task Derailment | 1.000 | 0.600 | 0.750 | 0.971 | 15 |
| F7 | Context Neglect | 0.465 | 0.952 | 0.625 | 0.650 | 63 |
| F8 | Information Withholding | 0.756 | 0.608 | 0.674 | 0.854 | 51 |
| F9 | Role Usurpation | 0.750 | 0.600 | 0.667 | 0.971 | 10 |

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
Actual Pos     65      1  (TP, FN)
       Neg     64     76  (FP, TN)
```

### F11: Coordination Failure

```
              Predicted
            Pos    Neg
Actual Pos    108      2  (TP, FN)
       Neg     47     49  (FP, TN)
```

### F12: Output Validation Failure

```
              Predicted
            Pos    Neg
Actual Pos     47      3  (TP, FN)
       Neg     59     97  (FP, TN)
```

### F13: Quality Gate Bypass

```
              Predicted
            Pos    Neg
Actual Pos     30     12  (TP, FN)
       Neg      3    161  (FP, TN)
```

### F14: Completion Misjudgment

```
              Predicted
            Pos    Neg
Actual Pos     43      2  (TP, FN)
       Neg     73     88  (FP, TN)
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
Actual Pos     81      7  (TP, FN)
       Neg     58     60  (FP, TN)
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
Actual Pos     61      6  (TP, FN)
       Neg     57     82  (FP, TN)
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
Actual Pos     60      3  (TP, FN)
       Neg     69     74  (FP, TN)
```

### F8: Information Withholding

```
              Predicted
            Pos    Neg
Actual Pos     31     20  (TP, FN)
       Neg     10    145  (FP, TN)
```

### F9: Role Usurpation

```
              Predicted
            Pos    Neg
Actual Pos      6      4  (TP, FN)
       Neg      2    194  (FP, TN)
```
