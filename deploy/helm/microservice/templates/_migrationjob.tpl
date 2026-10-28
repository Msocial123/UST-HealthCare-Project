{{- /* Runs `alembic upgrade head` once per sync, after the secret exists and before the new pods roll out. */ -}}
{{- define "microservice.migrationjob" -}}
apiVersion: batch/v1
kind: Job
metadata:
  name: {{ include "microservice.name" . }}-migrate
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
  annotations:
    argocd.argoproj.io/hook: Sync
    argocd.argoproj.io/hook-delete-policy: BeforeHookCreation
    argocd.argoproj.io/sync-wave: "-1"
spec:
  backoffLimit: {{ .Values.migrations.backoffLimit }}
  activeDeadlineSeconds: 600
  template:
    metadata:
      labels:
        {{- include "microservice.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: migration
    spec:
      restartPolicy: Never
      serviceAccountName: {{ include "microservice.name" . }}
      securityContext:
        {{- include "microservice.podSecurityContext" . | nindent 8 }}
      containers:
        - name: migrate
          image: {{ include "microservice.image" . }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          command: ["alembic", "upgrade", "head"]
          envFrom:
            {{- include "microservice.envFrom" . | nindent 12 }}
          securityContext:
            {{- include "microservice.containerSecurityContext" . | nindent 12 }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
{{- end -}}
