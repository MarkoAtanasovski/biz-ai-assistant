# Stage 1: build the jar with Maven. This stage has the JDK and Maven,
# but none of that ends up in the final image.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
# Copy pom.xml first and download dependencies before copying source.
# Docker caches each step: if only your .java files change later,
# this dependency download is skipped on the next build.
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
# Tests run in CI (and with `mvn test`), not on every image build.
RUN mvn package -DskipTests

# Stage 2: the actual runtime image. Just a JRE plus the one jar file.
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
RUN addgroup -S app && adduser -S app -G app
COPY --from=build /build/target/*.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
