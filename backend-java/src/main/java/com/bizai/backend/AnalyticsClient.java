package com.bizai.backend;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;
import java.util.Map;

@Component
public class AnalyticsClient {

    // Generic types are erased at runtime, so we keep these "type tokens"
    // to tell Jackson what shape of JSON to expect back from Python.
    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<Map<String, Object>>() {};
    private static final ParameterizedTypeReference<List<Map<String, Object>>> LIST_TYPE =
            new ParameterizedTypeReference<List<Map<String, Object>>>() {};

    private final WebClient webClient;

    public AnalyticsClient(WebClient.Builder builder,
                           @Value("${analytics.base-url}") String baseUrl) {
        this.webClient = builder.baseUrl(baseUrl).build();
    }

    public Map<String, Object> getSummary(List<Sale> sales) {
        return post("/analytics/summary", sales, MAP_TYPE);
    }

    public List<Map<String, Object>> getByRegion(List<Sale> sales) {
        return post("/analytics/by-region", sales, LIST_TYPE);
    }

    public List<Map<String, Object>> getByProduct(List<Sale> sales) {
        return post("/analytics/by-product", sales, LIST_TYPE);
    }

    // The AI endpoint takes an object, not a bare list:
    // {"question": "...", "sales": [ ...rows... ]}
    public Map<String, Object> ask(String question, List<Sale> sales) {
        Map<String, Object> body = Map.of("question", question, "sales", sales);
        return post("/ai/ask", body, MAP_TYPE);
    }

    // One place for the request logic. The body can be any object
    // (a list of sales, a map, ...); Jackson turns it into JSON.
    private <T> T post(String path, Object body, ParameterizedTypeReference<T> type) {
        return webClient.post()
                .uri(path)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(type)
                .block();
    }
}
