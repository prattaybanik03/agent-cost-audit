# The image generated code is tested in. It is run with --network none.
# The base image is pinned by digest (python:3.12-slim, Python 3.12.16, resolved 2026-11-19), so a
# rebuild gets the same image. pytest is the only package installed, pinned to the version in
# uv.lock.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

RUN pip install --no-cache-dir pytest==9.2.0

WORKDIR /work
