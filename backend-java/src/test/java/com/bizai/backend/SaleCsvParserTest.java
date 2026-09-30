package com.bizai.backend;

import org.junit.jupiter.api.Test;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SaleCsvParserTest {

    private static List<Sale> parse(String csv) {
        return SaleCsvParser.parse(new ByteArrayInputStream(csv.getBytes(StandardCharsets.UTF_8)));
    }

    private static String errorFor(String csv) {
        return assertThrows(CsvImportException.class, () -> parse(csv)).getMessage();
    }

    @Test
    void parsesPlainCsv() {
        List<Sale> sales = parse("region,product,revenue,units_sold,month\nLjubljana,Widget A,12500.50,340,2026-07\n");
        assertEquals(1, sales.size());
        Sale s = sales.get(0);
        assertEquals("Ljubljana", s.getRegion());
        assertEquals(12500.50, s.getRevenue());
        assertEquals(340, s.getUnitsSold());
        assertEquals("2026-07", s.getMonth());
    }

    @Test
    void headerNamesAreForgiving() {
        List<Sale> sales = parse("Month,Units Sold,REVENUE,Product,Region\n2026-08,10,99,Widget B,Maribor\n");
        assertEquals("Maribor", sales.get(0).getRegion());
        assertEquals(10, sales.get(0).getUnitsSold());
    }

    @Test
    void handlesExcelStyleSemicolonFileWithBomAndDecimalComma() {
        String csv = "\uFEFFregion;product;revenue;units_sold;month\nMaribor;Widget A;6100,75;165;2026-07\n";
        Sale s = parse(csv).get(0);
        assertEquals(6100.75, s.getRevenue());
        assertEquals(165, s.getUnitsSold());
    }

    @Test
    void quotedFieldsMayContainTheDelimiter() {
        Sale s = parse("region,product,revenue,units_sold,month\n\"Ljubljana, Center\",Widget A,1,1,2026-07\n").get(0);
        assertEquals("Ljubljana, Center", s.getRegion());
    }

    @Test
    void fullDatesAreReducedToTheMonth() {
        assertEquals("2026-07", parse("region,product,revenue,units_sold,month\nA,B,1,1,2026-07-15\n").get(0).getMonth());
    }

    @Test
    void reportsMissingColumns() {
        String msg = errorFor("region,product,revenue\nA,B,1\n");
        assertTrue(msg.contains("units_sold") && msg.contains("month"), msg);
    }

    @Test
    void reportsTheRowOfABadNumber() {
        String msg = errorFor("region,product,revenue,units_sold,month\nA,B,1,1,2026-07\nA,B,abc,1,2026-07\n");
        assertTrue(msg.startsWith("Data row 2") && msg.contains("revenue"), msg);
    }

    @Test
    void rejectsBadMonthsEmptyValuesAndEmptyFiles() {
        assertTrue(errorFor("region,product,revenue,units_sold,month\nA,B,1,1,July\n").contains("month"));
        assertTrue(errorFor("region,product,revenue,units_sold,month\n,B,1,1,2026-07\n").contains("'region' is empty"));
        assertTrue(errorFor("").contains("empty"));
        assertTrue(errorFor("region,product,revenue,units_sold,month\n").contains("no data rows"));
    }
}
