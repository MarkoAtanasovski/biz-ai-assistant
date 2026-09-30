package com.bizai.backend;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

import java.io.IOException;
import java.io.InputStream;
import java.io.StringReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Turns an uploaded CSV into Sale objects, or explains exactly what is wrong.
 *
 * Accepted columns (any order, header names are case/underscore-insensitive):
 *   region, product, revenue, units_sold (or unitsSold), month (YYYY-MM)
 *
 * Handles what Excel really produces: a UTF-8 BOM, and in European locales
 * a semicolon delimiter with decimal commas (12500,50). Nothing is saved
 * here; the caller only touches the database if parsing succeeds.
 */
public final class SaleCsvParser {

    public static final int MAX_ROWS = 20_000;
    private static final int MAX_TEXT_LENGTH = 255;

    // 2026-07 or a full date like 2026-07-15 (the day is dropped)
    private static final Pattern MONTH = Pattern.compile("^(\\d{4}-(?:0[1-9]|1[0-2]))(?:-\\d{2})?$");
    private static final Pattern DECIMAL = Pattern.compile("^-?\\d+(\\.\\d+)?$");
    private static final Pattern WHOLE = Pattern.compile("^(\\d+)(\\.0+)?$");
    private static final List<String> REQUIRED = List.of("region", "product", "revenue", "unitssold", "month");

    private SaleCsvParser() {
    }

    public static List<Sale> parse(InputStream in) {
        String content;
        try {
            content = new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new CsvImportException("Could not read the file: " + e.getMessage());
        }
        if (!content.isEmpty() && content.charAt(0) == '\uFEFF') {
            content = content.substring(1); // Excel's byte-order mark
        }
        if (content.isBlank()) {
            throw new CsvImportException("The file is empty.");
        }

        char delimiter = detectDelimiter(content);
        boolean decimalComma = delimiter == ';';
        CSVFormat format = CSVFormat.DEFAULT.builder()
                .setDelimiter(delimiter)
                .setHeader()               // take the header from the first line
                .setSkipHeaderRecord(true)
                .setIgnoreEmptyLines(true)
                .setTrim(true)
                .build();

        try (CSVParser parser = CSVParser.parse(new StringReader(content), format)) {
            Map<String, String> columns = mapColumns(parser.getHeaderNames());
            List<Sale> sales = new ArrayList<>();
            int row = 0;
            for (CSVRecord record : parser) {
                row++;
                if (row > MAX_ROWS) {
                    throw new CsvImportException("Too many rows: the limit is " + MAX_ROWS + ".");
                }
                sales.add(toSale(record, columns, row, decimalComma));
            }
            if (sales.isEmpty()) {
                throw new CsvImportException("The file has a header but no data rows.");
            }
            return sales;
        } catch (IOException | IllegalArgumentException e) {
            throw new CsvImportException("Could not read the CSV: " + e.getMessage());
        }
    }

    private static char detectDelimiter(String content) {
        String text = content.stripLeading();
        int end = text.indexOf('\n');
        String firstLine = end < 0 ? text : text.substring(0, end);
        long commas = firstLine.chars().filter(c -> c == ',').count();
        long semicolons = firstLine.chars().filter(c -> c == ';').count();
        long tabs = firstLine.chars().filter(c -> c == '\t').count();
        if (semicolons > commas && semicolons >= tabs) return ';';
        if (tabs > commas && tabs > semicolons) return '\t';
        return ',';
    }

    private static String normalize(String header) {
        return header.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    /** normalized name -> the header text as it appears in the file */
    private static Map<String, String> mapColumns(List<String> headers) {
        Map<String, String> byKey = new HashMap<>();
        for (String header : headers) {
            if (header != null) byKey.putIfAbsent(normalize(header), header);
        }
        List<String> missing = REQUIRED.stream()
                .filter(key -> !byKey.containsKey(key))
                .map(key -> key.equals("unitssold") ? "units_sold" : key)
                .toList();
        if (!missing.isEmpty()) {
            throw new CsvImportException("Missing required column(s): " + String.join(", ", missing)
                    + ". Expected a header row with: region, product, revenue, units_sold, month.");
        }
        return byKey;
    }

    private static Sale toSale(CSVRecord record, Map<String, String> columns, int row, boolean decimalComma) {
        String region = text(record, columns, "region", "region", row);
        String product = text(record, columns, "product", "product", row);
        double revenue = parseRevenue(text(record, columns, "revenue", "revenue", row), decimalComma, row);
        int units = parseUnits(text(record, columns, "unitssold", "units_sold", row), row);
        String month = parseMonth(text(record, columns, "month", "month", row), row);
        return new Sale(region, product, revenue, units, month);
    }

    private static String text(CSVRecord record, Map<String, String> columns, String key, String label, int row) {
        String header = columns.get(key);
        String value = record.isSet(header) ? record.get(header) : null;
        if (value == null || value.isBlank()) {
            throw new CsvImportException("Data row " + row + ": '" + label + "' is empty.");
        }
        value = value.trim();
        if (value.length() > MAX_TEXT_LENGTH) {
            throw new CsvImportException("Data row " + row + ": '" + label + "' is longer than "
                    + MAX_TEXT_LENGTH + " characters.");
        }
        return value;
    }

    private static double parseRevenue(String raw, boolean decimalComma, int row) {
        String s = raw.replace(" ", "").replace("\u00A0", "");
        if (decimalComma) s = s.replace(',', '.'); // 12500,50 -> 12500.50
        if (!DECIMAL.matcher(s).matches()) {
            throw new CsvImportException("Data row " + row + ": revenue '" + raw + "' is not a plain number "
                    + "(no currency symbols or thousands separators).");
        }
        return Double.parseDouble(s);
    }

    private static int parseUnits(String raw, int row) {
        Matcher m = WHOLE.matcher(raw.replace(" ", ""));
        if (m.matches()) {
            try {
                return Integer.parseInt(m.group(1));
            } catch (NumberFormatException ignored) {
                // too big for an int: fall through to the error below
            }
        }
        throw new CsvImportException("Data row " + row + ": units_sold '" + raw + "' is not a whole number.");
    }

    private static String parseMonth(String raw, int row) {
        Matcher m = MONTH.matcher(raw);
        if (!m.matches()) {
            throw new CsvImportException("Data row " + row + ": month '" + raw + "' must look like 2026-07.");
        }
        return m.group(1);
    }
}
