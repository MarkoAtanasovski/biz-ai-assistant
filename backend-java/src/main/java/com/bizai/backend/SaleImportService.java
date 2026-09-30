package com.bizai.backend;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class SaleImportService {

    public record ImportResult(int imported, String mode, long totalRows) {}

    private final SaleRepository saleRepository;

    public SaleImportService(SaleRepository saleRepository) {
        this.saleRepository = saleRepository;
    }

    /**
     * One transaction: if saving fails half-way, a "replace" does not
     * leave the table wiped. (Parsing already succeeded before we get here.)
     */
    @Transactional
    public ImportResult save(List<Sale> sales, boolean replace) {
        if (replace) {
            saleRepository.deleteAllInBatch();
        }
        saleRepository.saveAll(sales);
        return new ImportResult(sales.size(), replace ? "replace" : "append", saleRepository.count());
    }
}
