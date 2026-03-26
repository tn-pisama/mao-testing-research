{{/*
Expand the name of the chart.
*/}}
{{- define "pisama.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this
(by the DNS naming spec). If release name contains chart name it will be used
as a full name.
*/}}
{{- define "pisama.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "pisama.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "pisama.labels" -}}
helm.sh/chart: {{ include "pisama.chart" . }}
{{ include "pisama.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "pisama.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pisama.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend name.
*/}}
{{- define "pisama.backend.name" -}}
{{- printf "%s-backend" (include "pisama.fullname" .) }}
{{- end }}

{{/*
Backend labels.
*/}}
{{- define "pisama.backend.labels" -}}
{{ include "pisama.labels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Backend selector labels.
*/}}
{{- define "pisama.backend.selectorLabels" -}}
{{ include "pisama.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend name.
*/}}
{{- define "pisama.frontend.name" -}}
{{- printf "%s-frontend" (include "pisama.fullname" .) }}
{{- end }}

{{/*
Frontend labels.
*/}}
{{- define "pisama.frontend.labels" -}}
{{ include "pisama.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Frontend selector labels.
*/}}
{{- define "pisama.frontend.selectorLabels" -}}
{{ include "pisama.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Service account name.
*/}}
{{- define "pisama.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "pisama.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database host: use subchart service or external host.
*/}}
{{- define "pisama.database.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" .Release.Name }}
{{- else }}
{{- .Values.externalDatabase.host }}
{{- end }}
{{- end }}

{{/*
Database port.
*/}}
{{- define "pisama.database.port" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "5432" }}
{{- else }}
{{- printf "%d" (int .Values.externalDatabase.port) }}
{{- end }}
{{- end }}

{{/*
Database user.
*/}}
{{- define "pisama.database.user" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.username }}
{{- else }}
{{- .Values.externalDatabase.user }}
{{- end }}
{{- end }}

{{/*
Database name.
*/}}
{{- define "pisama.database.name" -}}
{{- if .Values.postgresql.enabled }}
{{- .Values.postgresql.auth.database }}
{{- else }}
{{- .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Redis host: use subchart service or external host.
*/}}
{{- define "pisama.redis.host" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" .Release.Name }}
{{- else }}
{{- .Values.externalRedis.host }}
{{- end }}
{{- end }}

{{/*
Redis port.
*/}}
{{- define "pisama.redis.port" -}}
{{- if .Values.redis.enabled }}
{{- printf "6379" }}
{{- else }}
{{- printf "%d" (int .Values.externalRedis.port) }}
{{- end }}
{{- end }}

{{/*
Construct DATABASE_URL.
*/}}
{{- define "pisama.database.url" -}}
{{- printf "postgresql+asyncpg://%s:$(DATABASE_PASSWORD)@%s:%s/%s" (include "pisama.database.user" .) (include "pisama.database.host" .) (include "pisama.database.port" .) (include "pisama.database.name" .) }}
{{- end }}

{{/*
Construct REDIS_URL.
*/}}
{{- define "pisama.redis.url" -}}
{{- printf "redis://%s:%s/0" (include "pisama.redis.host" .) (include "pisama.redis.port" .) }}
{{- end }}

{{/*
Secret name for the chart.
*/}}
{{- define "pisama.secret.name" -}}
{{- printf "%s-secrets" (include "pisama.fullname" .) }}
{{- end }}

{{/*
ConfigMap name for the chart.
*/}}
{{- define "pisama.configmap.name" -}}
{{- printf "%s-config" (include "pisama.fullname" .) }}
{{- end }}

{{/*
Image pull secrets.
*/}}
{{- define "pisama.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}
