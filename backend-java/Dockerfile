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
RUN mvn package -DskipTests

# Stage 2: the actual runtime image. Just a JRE (no compiler, no
# Maven) plus the one jar file - much smaller than stage 1.
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
