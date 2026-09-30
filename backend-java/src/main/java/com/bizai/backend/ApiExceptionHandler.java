package com.bizai.backend;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.Map;

/**
 * Every error the frontend can see has the same shape, {"detail": "..."},
 * the same key FastAPI uses, so the UI has a single thing to read.
 */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static ResponseEntity<Map<String, String>> detail(HttpStatus status, String message) {
        return ResponseEntity.status(status).body(Map.of("detail", message));
    }

    @ExceptionHandler(CsvImportException.class)
    public ResponseEntity<Map<String, String>> badCsv(CsvImportException e) {
        return detail(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<Map<String, String>> tooLarge() {
        return detail(HttpStatus.PAYLOAD_TOO_LARGE, "The file is too large (limit 5 MB).");
    }

    // Python is down or unreachable: 503 instead of a raw 500 with a stack trace.
    @ExceptionHandler(WebClientRequestException.class)
    public ResponseEntity<Map<String, String>> analyticsUnreachable() {
        return detail(HttpStatus.SERVICE_UNAVAILABLE, "Analytics service is unreachable.");
    }

    // Python did not answer in time.
    @ExceptionHandler(AnalyticsTimeoutException.class)
    public ResponseEntity<Map<String, String>> analyticsTimeout(AnalyticsTimeoutException e) {
        return detail(HttpStatus.GATEWAY_TIMEOUT, e.getMessage());
    }

    // Python answered, but with an error (400 empty question, 503 missing
    // Gemini key, 502 Gemini failed...). Pass its status and body on unchanged.
    @ExceptionHandler(WebClientResponseException.class)
    public ResponseEntity<String> analyticsError(WebClientResponseException e) {
        return ResponseEntity.status(e.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(e.getResponseBodyAsString());
    }
}
