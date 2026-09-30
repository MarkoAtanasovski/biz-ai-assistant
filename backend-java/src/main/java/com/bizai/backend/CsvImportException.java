package com.bizai.backend;

/** The uploaded file (or the upload request) is not something we can import. Mapped to HTTP 400. */
public class CsvImportException extends RuntimeException {
    public CsvImportException(String message) {
        super(message);
    }
}
