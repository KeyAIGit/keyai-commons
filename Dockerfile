FROM golang:1.27.1-alpine AS builder
WORKDIR /src
COPY src/ ./
RUN go test -count=1 ./... && CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /commons .
FROM alpine:3.23
RUN addgroup -g 1000 commons && adduser -D -u 1000 -G commons commons && mkdir /state && chown commons:commons /state
COPY --from=builder /commons /usr/local/bin/keyai-commons
USER 1000:1000
EXPOSE 7860
ENTRYPOINT ["keyai-commons"]
CMD ["coordinator", "--listen", "0.0.0.0:7860", "--data", "/state", "--no-browser"]
