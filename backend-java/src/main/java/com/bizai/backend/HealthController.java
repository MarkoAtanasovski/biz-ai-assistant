package com.bizai.backend;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * @RestController tells Spring: "instances of this class handle incoming
 * HTTP requests, and every method's return value should be serialized
 * straight to JSON in the response body."
 *
 * This is the Java equivalent of:
 *   const router = express.Router();
 *   router.get('/api/health', (req, res) => res.json({ status: 'ok' }));
 */
@RestController
public class HealthController {

    // @GetMapping maps HTTP GET requests at this path to this method.
    // Spring automatically converts the returned Map into a JSON object
    // like: {"status":"ok","service":"biz-ai-backend"}
    @GetMapping("/api/health")
    public Map<String, String> health() {
        return Map.of(
                "status", "ok",
                "service", "biz-ai-backend"
        );
    }
}
