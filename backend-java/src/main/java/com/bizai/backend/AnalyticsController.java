package com.bizai.backend;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

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

    // Java owns the data: read the rows from the database and hand them to Python.
    @GetMapping("/api/analytics/summary")
    public Map<String, Object> summary() {
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

    @GetMapping("/api/analytics/by-month")
    public List<Map<String, Object>> byMonth() {
        return analyticsClient.getByMonth(saleRepository.findAll());
    }

    @PostMapping("/api/ai/ask")
    public Map<String, Object> ask(@RequestBody AskRequest request) {
        // Map.of() rejects null values, so turn a missing question into "" and
        // let Python answer with its own 400 "must not be empty".
        String question = request.question() == null ? "" : request.question();
        return analyticsClient.ask(question, saleRepository.findAll());
    }
}
