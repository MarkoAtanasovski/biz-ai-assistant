package com.bizai.backend;

import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

@RestController
public class SaleController {

    private final SaleRepository saleRepository;
    private final SaleImportService importService;

    public SaleController(SaleRepository saleRepository, SaleImportService importService) {
        this.saleRepository = saleRepository;
        this.importService = importService;
    }

    // GET /api/sales -> returns every row in the sale table as JSON
    @GetMapping("/api/sales")
    public List<Sale> getAllSales() {
        return saleRepository.findAll();
    }

    /**
     * POST /api/sales/upload  (multipart: file=<csv>, mode=replace|append)
     * The file is fully parsed and validated first; the database is only
     * touched if every row is valid.
     */
    @PostMapping("/api/sales/upload")
    public SaleImportService.ImportResult upload(@RequestParam("file") MultipartFile file,
                                                 @RequestParam(name = "mode", defaultValue = "replace") String mode) {
        if (!mode.equals("replace") && !mode.equals("append")) {
            throw new CsvImportException("mode must be 'replace' or 'append'.");
        }
        if (file.isEmpty()) {
            throw new CsvImportException("No file was uploaded.");
        }
        List<Sale> sales;
        try (InputStream in = file.getInputStream()) {
            sales = SaleCsvParser.parse(in);
        } catch (IOException e) {
            throw new CsvImportException("Could not read the file: " + e.getMessage());
        }
        return importService.save(sales, mode.equals("replace"));
    }

    /**
     * Seeds demo data on first start only. With PostgreSQL the data now
     * survives restarts, so we must not add the same rows again each time.
     * Turn off with app.seed-demo-data=false.
     */
    @Component
    @ConditionalOnProperty(name = "app.seed-demo-data", havingValue = "true", matchIfMissing = true)
    static class DataSeeder implements CommandLineRunner {
        private final SaleRepository saleRepository;

        DataSeeder(SaleRepository saleRepository) {
            this.saleRepository = saleRepository;
        }

        @Override
        public void run(String... args) {
            if (saleRepository.count() > 0) {
                return;
            }
            saleRepository.save(new Sale("Ljubljana", "Widget A", 12500.0, 340, "2026-07"));
            saleRepository.save(new Sale("Ljubljana", "Widget B", 8200.0, 210, "2026-07"));
            saleRepository.save(new Sale("Maribor", "Widget A", 6100.0, 165, "2026-07"));
            saleRepository.save(new Sale("Ljubljana", "Widget A", 14300.0, 390, "2026-08"));
            saleRepository.save(new Sale("Maribor", "Widget B", 5400.0, 140, "2026-08"));
        }
    }
}
