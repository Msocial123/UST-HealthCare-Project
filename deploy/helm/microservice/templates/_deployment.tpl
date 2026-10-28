{{- define "microservice.deployment" -}}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "microservice.name" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.replicaCount }}
  revisionHistoryLimit: {{ .Values.revisionHistoryLimit }}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      {{- include "microservice.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "microservice.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/part-of: smart-hospital
        app.kubernetes.io/version: {{ .Values.image.tag | quote }}
      annotations:
        checksum/config: {{ include "microservice.configmap" . | sha256sum }}
    spec:
      serviceAccountName: {{ include "microservice.name" . }}
      automountServiceAccountToken: false
      securityContext:
        {{- include "microservice.podSecurityContext" . | nindent 8 }}
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              {{- include "microservice.selectorLabels" . | nindent 14 }}
      containers:
        - name: app
          image: {{ include "microservice.image" . }}
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.containerPort }}
              protocol: TCP
          envFrom:
            {{- include "microservice.envFrom" . | nindent 12 }}
          startupProbe:
            httpGet:
              path: {{ .Values.probes.livenessPath }}
              port: http
            periodSeconds: 5
            failureThreshold: 24
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.livenessPath }}
              port: http
            periodSeconds: 15
            timeoutSeconds: 3
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readinessPath }}
              port: http
            periodSeconds: 10
            timeoutSeconds: 3
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
