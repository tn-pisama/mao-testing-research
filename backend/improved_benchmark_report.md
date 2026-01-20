# MAST Benchmark Report

**Generated:** 2026-01-16 23:38:02 UTC
**Run ID:** 19eca68d
**Duration:** 44.6 seconds

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Records | 1,242 |
| Processed | 1,242 |
| Detections | 1,211 |
| Macro F1 | 0.141 |
| Micro F1 | 0.269 |
| Weighted F1 | 0.221 |
| Overall Accuracy | 70.1% |
| ECE (Calibration) | 0.196 |
| Mean Latency | 0.3 ms/record |

## Per-Failure-Mode Results

### Low Performance (F1 < 0.50)

| Mode | Name | Precision | Recall | F1 | Accuracy | Support |
|------|------|----------:|-------:|---:|---------:|--------:|
| F13 | Quality Gate Bypass | 0.000 | 0.000 | 0.000 | 0.796 | 42 |
| F4 | Inadequate Tool Provision | 0.091 | 0.091 | 0.091 | 0.806 | 22 |
| F5 | Flawed Workflow Design | 0.303 | 0.791 | 0.438 | 0.340 | 67 |
| F6 | Task Derailment | 0.029 | 0.133 | 0.048 | 0.617 | 15 |
| F8 | Information Withholding | 0.355 | 0.216 | 0.268 | 0.709 | 51 |
| F9 | Role Usurpation | 0.000 | 0.000 | 0.000 | 0.937 | 10 |

## Confusion Matrices

### F13: Quality Gate Bypass

```
              Predicted
            Pos    Neg
Actual Pos      0     42  (TP, FN)
       Neg      0    164  (FP, TN)
```

### F4: Inadequate Tool Provision

```
              Predicted
            Pos    Neg
Actual Pos      2     20  (TP, FN)
       Neg     20    164  (FP, TN)
```

### F5: Flawed Workflow Design

```
              Predicted
            Pos    Neg
Actual Pos     53     14  (TP, FN)
       Neg    122     17  (FP, TN)
```

### F6: Task Derailment

```
              Predicted
            Pos    Neg
Actual Pos      2     13  (TP, FN)
       Neg     66    125  (FP, TN)
```

### F8: Information Withholding

```
              Predicted
            Pos    Neg
Actual Pos     11     40  (TP, FN)
       Neg     20    135  (FP, TN)
```

### F9: Role Usurpation

```
              Predicted
            Pos    Neg
Actual Pos      0     10  (TP, FN)
       Neg      3    193  (FP, TN)
```
