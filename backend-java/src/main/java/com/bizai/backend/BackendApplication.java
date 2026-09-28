package com.bizai.backend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Entry point of the application.
 *
 * @SpringBootApplication is a shortcut annotation that combines three things:
 *   1. @Configuration   - this class can define Spring beans/config
 *   2. @EnableAutoConfiguration - Spring guesses sensible config based on
 *                          what's on the classpath (e.g. "web starter is
 *                          present -> configure an embedded Tomcat server")
 *   3. @ComponentScan   - Spring will scan this package (and sub-packages)
 *                          for classes annotated with @RestController,
 *                          @Service, @Component, etc. and wire them together
 *                          automatically (this is "dependency injection").
 *
 * This is conceptually similar to how in Express you'd write:
 *   const app = express();
 *   app.listen(8080);
 * ...except Spring does a lot more automatic wiring behind the scenes.
 */
@SpringBootApplication
public class BackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(BackendApplication.class, args);
    }
}
