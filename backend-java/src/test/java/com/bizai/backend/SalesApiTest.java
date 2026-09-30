package com.bizai.backend;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

import static org.hamcrest.Matchers.containsString;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Boots the whole Spring app against in-memory H2 and drives it over HTTP.
 * The Python service is replaced by a mock, so this needs no other process.
 */
@SpringBootTest
@AutoConfigureMockMvc
class SalesApiTest {

    private static final String HEADER = "region,product,revenue,units_sold,month\n";

    @Autowired MockMvc mvc;
    @Autowired SaleRepository saleRepository;
    @MockBean AnalyticsClient analyticsClient;

    @BeforeEach
    void emptyTable() {
        saleRepository.deleteAll();
    }

    private static MockMultipartFile csv(String body) {
        return new MockMultipartFile("file", "sales.csv", "text/csv", body.getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void uploadReplacesDataAndItCanBeReadBack() throws Exception {
        saleRepository.save(new Sale("Old", "Old", 1.0, 1, "2020-01"));

        mvc.perform(multipart("/api/sales/upload").file(csv(HEADER + "Ljubljana,Widget A,100,2,2026-07\nMaribor,Widget B,50,1,2026-08\n")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.imported").value(2))
                .andExpect(jsonPath("$.mode").value("replace"))
                .andExpect(jsonPath("$.totalRows").value(2));

        mvc.perform(get("/api/sales"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].region").value("Ljubljana"));
    }

    @Test
    void appendKeepsExistingRows() throws Exception {
        saleRepository.save(new Sale("Old", "Old", 1.0, 1, "2020-01"));

        mvc.perform(multipart("/api/sales/upload").file(csv(HEADER + "New,Widget A,5,1,2026-07\n")).param("mode", "append"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalRows").value(2));
    }

    @Test
    void badCsvIsRejectedAndExistingDataSurvives() throws Exception {
        saleRepository.save(new Sale("Keep", "Me", 1.0, 1, "2020-01"));

        mvc.perform(multipart("/api/sales/upload").file(csv(HEADER + "A,B,not-a-number,1,2026-07\n")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").value(containsString("Data row 1")));

        mvc.perform(get("/api/sales"))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].region").value("Keep"));
    }

    @Test
    void analyticsAreComputedFromWhatIsInTheDatabase() throws Exception {
        saleRepository.save(new Sale("Ljubljana", "Widget A", 100.0, 2, "2026-07"));
        saleRepository.save(new Sale("Maribor", "Widget A", 50.0, 1, "2026-07"));
        when(analyticsClient.getSummary(anyList())).thenReturn(Map.of("total_revenue", 150.0));

        mvc.perform(get("/api/analytics/summary"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total_revenue").value(150.0));

        // Java, not Python, owns the data: both stored rows were sent along.
        verify(analyticsClient).getSummary(argThat((List<Sale> rows) -> rows.size() == 2));
    }

    @Test
    void slowPythonBecomes504WithADetailMessage() throws Exception {
        when(analyticsClient.getSummary(anyList())).thenThrow(new AnalyticsTimeoutException("too slow"));

        mvc.perform(get("/api/analytics/summary"))
                .andExpect(status().isGatewayTimeout())
                .andExpect(jsonPath("$.detail").value("too slow"));
    }
}
