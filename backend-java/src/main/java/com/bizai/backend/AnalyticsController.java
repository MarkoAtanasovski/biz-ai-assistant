package com.bizai.backend;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.List;
import java.util.Map;

@RestController
public class AnalyticsController {

    // The JSON body clients send to /api/ai/ask: {"question": "..."}
    public record AskRequest(String question) {}

    private final AnalyticsClient analyticsClient;
    private final SaleRepository saleRepository;

    public AnalyticsController(AnalyticsClient analyticsClient,
                               SaleRepository saleRepository) {
        this.analyticsClient = analyticsClient;
        this.saleRepository = saleRepository;
    }

    @GetMapping("/api/analytics/summary")
    public Map<String, Object> summary() {
        // Java owns the data: read the rows from H2 and hand them to Python.
        return analyticsClient.getSummary(saleRepository.findAll());
    }

    @GetMapping("/api/analytics/by-region")
    public List<Map<String, Object>> byRegion() {
        return analyticsClient.getByRegion(saleRepository.findAll());
    }

    @GetMapping("/api/analytics/by-product")
    public List<Map<String, Object>> byProduct() {
        return analyticsClient.getByProduct(saleRepository.findAll());
    }

    @PostMapping("/api/ai/ask")
    public Map<String, Object> ask(@RequestBody AskRequest request) {
        // Map.of() rejects null values, so turn a missing question into ""
        // and let Python answer with its own 400 "must not be empty".
        String question = request.question() == null ? "" : request.question();
        return analyticsClient.ask(question, saleRepository.findAll());
    }

    // Python is down or unreachable: 503 ("a dependency is unavailable")
    // instead of a raw 500 with a stack trace.
    @ExceptionHandler(WebClientRequestException.class)
    public ResponseEntity<Map<String, String>> analyticsUnreachable() {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("error", "Analytics service is unreachable"));
    }

    // Python answered, but with an error (400 empty question, 503 missing
    // Gemini key, 502 Gemini failed...). Pass its status and message on
    // unchanged instead of hiding it behind a generic 500.
    @ExceptionHandler(WebClientResponseException.class)
    public ResponseEntity<String> analyticsError(WebClientResponseException e) {
        return ResponseEntity.status(e.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(e.getResponseBodyAsString());
    }
}
