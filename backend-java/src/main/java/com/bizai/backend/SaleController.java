package com.bizai.backend;

import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class SaleController {

    // Spring automatically "injects" a working SaleRepository here for us
    // (this is what @ComponentScan/dependency injection, mentioned back
    // in BackendApplication.java, actually does in practice).
    private final SaleRepository saleRepository;

    public SaleController(SaleRepository saleRepository) {
        this.saleRepository = saleRepository;
    }

    // GET /api/sales -> returns every row in the sale table as JSON
    @GetMapping("/api/sales")
    public List<Sale> getAllSales() {
        return saleRepository.findAll();
    }

    /**
     * This inner class runs once automatically when the app starts up.
     * CommandLineRunner is Spring's way of saying "run this code right
     * after the application context is ready." We use it here just to
     * seed some sample data into our in-memory H2 database, since H2
     * starts empty every time the app restarts.
     */
    @Component
    static class DataSeeder implements CommandLineRunner {
        private final SaleRepository saleRepository;

        DataSeeder(SaleRepository saleRepository) {
            this.saleRepository = saleRepository;
        }

        @Override
        public void run(String... args) {
            saleRepository.save(new Sale("Ljubljana", "Widget A", 12500.0, 340, "2026-07"));
            saleRepository.save(new Sale("Ljubljana", "Widget B", 8200.0, 210, "2026-07"));
            saleRepository.save(new Sale("Maribor", "Widget A", 6100.0, 165, "2026-07"));
            saleRepository.save(new Sale("Ljubljana", "Widget A", 14300.0, 390, "2026-08"));
            saleRepository.save(new Sale("Maribor", "Widget B", 5400.0, 140, "2026-08"));
        }
    }
}
