#!/usr/bin/with-contenv bashio
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")

apk add py3-scipy py3-statsmodels
ln -s /usr/lib/python${PYTHON_VERSION}/site-packages/scipy /usr/local/lib/python${PYTHON_VERSION}/site-packages/scipy
ln -s /usr/lib/python${PYTHON_VERSION}/site-packages/statsmodels /usr/local/lib/python${PYTHON_VERSION}/site-packages/statsmodels
