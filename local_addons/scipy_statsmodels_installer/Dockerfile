ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache py3-scipy py3-statsmodels && \
    ln -s /usr/lib/python3.12/site-packages/scipy /usr/local/lib/python3.12/site-packages/scipy && \
    ln -s /usr/lib/python3.12/site-packages/statsmodels /usr/local/lib/python3.12/site-packages/statsmodels

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD [ "/run.sh" ]


