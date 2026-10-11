# 构建阶段
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
COPY docker ./docker
RUN --mount=type=cache,target=/root/.m2 mvn -B -ntp clean verify && javac -d /tmp/healthcheck docker/HealthCheck.java

# 运行阶段
FROM eclipse-temurin:17-jre
WORKDIR /app
RUN mkdir -p /app/uploads && chown 10001:10001 /app/uploads
COPY --from=build /app/target/*.jar app.jar
COPY --from=build /tmp/healthcheck /app/healthcheck
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=12 CMD ["java", "-cp", "/app/healthcheck", "HealthCheck"]
ENTRYPOINT ["java", "-jar", "app.jar"]
