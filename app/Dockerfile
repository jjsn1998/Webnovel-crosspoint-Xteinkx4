FROM python:3.12-slim

RUN pip install --no-cache-dir beautifulsoup4 lxml ebooklib

WORKDIR /work

COPY html_to_epub.py /work/html_to_epub.py

ENTRYPOINT ["python", "/work/html_to_epub.py"]
