package com.bizai.backend;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeoutException;

@Component
public class AnalyticsClient {

    // Generic types are erased at runtime, so we keep these "type tokens"
    // to tell Jackson what shape of JSON to expect back from Python.
    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<Map<String, Object>>() {};
    private static final ParameterizedTypeReference<List<Map<String, Object>>> LIST_TYPE =
            new ParameterizedTypeReference<List<Map<String, Object>>>() {};

    private final WebClient webClient;
    private final Duration timeout;
    private final Duration askTimeout;

    public AnalyticsClient(WebClient.Builder builder,
                           @Value("${analytics.base-url}") String baseUrl,
                           @Value("${analytics.timeout-seconds:15}") long timeoutSeconds,
                           @Value("${analytics.ask-timeout-seconds:60}") long askTimeoutSeconds) {
        this.webClient = builder.baseUrl(baseUrl).build();
        this.timeout = Duration.ofSeconds(timeoutSeconds);
        this.askTimeout = Duration.ofSeconds(askTimeoutSeconds);
    }

    public Map<String, Object> getSummary(List<Sale> sales) {
        return post("/analytics/summary", sales, MAP_TYPE, timeout);
    }

    public List<Map<String, Object>> getByRegion(List<Sale> sales) {
        return post("/analytics/by-region", sales, LIST_TYPE, timeout);
    }

    public List<Map<String, Object>> getByProduct(List<Sale> sales) {
        return post("/analytics/by-product", sales, LIST_TYPE, timeout);
    }

    public List<Map<String, Object>> getByMonth(List<Sale> sales) {
        return post("/analytics/by-month", sales, LIST_TYPE, timeout);
    }

    // The AI endpoint takes an object, not a bare list:
    // {"question": "...", "sales": [ ...rows... ]}
    // It gets a longer timeout: Python may retry Gemini and run several
    // function-calling rounds.
    public Map<String, Object> ask(String question, List<Sale> sales) {
        Map<String, Object> body = Map.of("question", question, "sales", sales);
        return post("/ai/ask", body, MAP_TYPE, askTimeout);
    }

    // One place for the request logic. Without a timeout, a hung Python
    // service would hold a Tomcat thread forever.
    private <T> T post(String path, Object body, ParameterizedTypeReference<T> type, Duration limit) {
        return webClient.post()
                .uri(path)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(type)
                .timeout(limit)
                .onErrorMap(TimeoutException.class,
                        e -> new AnalyticsTimeoutException(
                                "Analytics service did not answer within " + limit.toSeconds() + " seconds"))
                .block();
    }
}
