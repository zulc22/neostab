UV_VERSION := $(shell uv version)

PROJECTNAME := $(word 1,${UV_VERSION})
VERSION := $(word 2,${UV_VERSION})

SRC_CONTENT := $(wildcard src/neostab/*)
DISTWHEEL := dist/${PROJECTNAME}-${VERSION}-py3-none-any.whl
DISTTARBALL := dist/${PROJECTNAME}-${VERSION}.tar.gz

default: ${DISTWHEEL}

.venv:
	uv run --managed-python -p 3.8 echo

${DISTWHEEL} ${DISTTARBALL}: ${SRC_CONTENT}
	uv build

upload_release: ${DISTWHEEL} ${DISTTARBALL}
	uv publish --username __token__

upload_test: ${DISTWHEEL} ${DISTTARBALL}
	uv publish --index testpypi --username __token__

clean:
	rm -rf dist .venv

.PHONY: default upload_release upload_test clean