FROM openjdk:11-jdk-slim

WORKDIR /app

COPY target/dameng-sql-scp-1.0-SNAPSHOT.jar app.jar

EXPOSE 18086

ENTRYPOINT ["java", "-jar", "app.jar"] 