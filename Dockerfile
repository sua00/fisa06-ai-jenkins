# =========================================================================
# FastAPI 애플리케이션 Dockerfile (멀티 스테이지 빌드 & 베스트 프랙티스 적용)
# 빌드 명령어: docker build -t my-fastapi-app .
# 실행 명령어: docker run -p 8000:8000 --env-file .env -v ./log:/app/log  my-fastapi-app
#           docker run -p 8000:8000 -v ./app/fastapi_app.log:/app/fastapi_app.log  my-fastapi-app
# =========================================================================

# -------------------------------------------------------------------------
# [Stage 1: Builder]
# 애플리케이션 실행에 필요한 패키지들을 빌드하고 모으는 첫 번째 단계입니다.
# -------------------------------------------------------------------------
FROM python:3.11-slim as builder

# 환경 변수 설정
# PYTHONDONTWRITEBYTECODE: 1로 설정하면 파이썬이 실행될 때 .pyc(바이트코드) 파일을 디스크에 강제로 쓰지 않도록 합니다. 
#                          어차피 컨테이너는 매번 새롭게 띄워지는 휘발성 환경이므로 .pyc 파일 찌꺼기를 남길 필요가 없으며, 이미지 크기를 줄이는 데 도움이 됩니다.
# PYTHONUNBUFFERED: 1로 설정하면 파이썬 출력이 버퍼를 거치지 않고 즉각적으로 터미널(로그)에 출력되게 합니다. 
#                   도커에서 FastAPI 앱이 충돌할 때 로그가 지연 없이 바로 보여 원인 파악이 훨씬 직관적입니다.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 빌드에 필요한 C 컴파일러(gcc) 등의 시스템 패키지를 설치합니다.
# (예: numpy, joblib, sqlalchemy 등 특정 파이썬 라이브러리 설치 시 C 컴파일이 필요할 수 있습니다.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

# 파이썬 가상 환경(virtualenv)을 /opt/venv 경로에 생성합니다.
# 이렇게 하면 나중에 두 번째 스테이지(Runner)로 설치된 의존성들을 통째로 복사하기 매우 편해집니다.
RUN python -m venv /opt/venv

# 가상 환경을 활성화하기 위해 환경 변수 PATH를 설정합니다. (이후 pip install 등은 이 안에서 실행됨)
ENV PATH="/opt/venv/bin:$PATH"

# 패키지 명세서(requirements.txt)만 먼저 복사하고 라이브러리를 설치합니다.
# 소스코드가 바뀌어도 패키지 재설치를 피하기 위한 도커 '캐시' 전략입니다.
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------------------
# [Stage 2: Runner]
# 실제로 서비스가 구동될 최종 환경을 구성하는 두 번째 단계입니다.
# Builder 단계에서 만들어진 결과물(가상 환경)만 가져오므로, 빌드 도구(gcc 등)가 빠져 최종 이미지가 가벼워집니다.
# -------------------------------------------------------------------------
FROM python:3.11-slim

# 환경 변수 설정
# (Builder 단계와 동일하게 pyc 쓰기 방지, 버퍼 없는 즉각적인 로그 출력을 위한 설정입니다.)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # 첫 번째 스테이지의 가상 환경을 사용하도록 PATH를 맞춥니다.
    PATH="/opt/venv/bin:$PATH"

# [보안 베스트 프랙티스] 루트(root) 권한으로 프로세스가 실행되는 것을 방지하기 위해 권한이 제한된 일반 유저를 생성합니다.
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 내부적으로 새로 생성되는 파일이 없다면 추가하지 않으셔도 됩니다.
# drwxr-xr-x   1 appuser appuser 4096 Apr  1 02:29 app
RUN mkdir -p /app && chown appuser:appuser /app
# 컨테이너 내부의 작업 폴더를 지정합니다.
WORKDIR /app

# Stage 1 (builder)에서 인스톨이 완료된 가상 환경 폴더 전체를 가져옵니다.
COPY --from=builder /opt/venv /opt/venv



# 실제 구동할 앱 전체 소스 코드를 복사합니다. 
# 파일의 소유권(chown)을 방금 새로 만든 일반 유저(appuser)로 지정합니다.
COPY --chown=appuser:appuser app/ /app/

# 이후 실행될 모든 명령어는 이 일반 유저 권한으로 실행되도록 합니다. (보안 강화)
USER appuser

# 외부에서 이 컨테이너로 접속할 포트를 명시합니다 (문서화 용도 및 컨테이너 간 통신 시 유용).
EXPOSE 8000

# 최종 실행 명령어 (0.0.0.0으로 띄워야 도커 컨테이너 외부에서 접근 가능합니다)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
