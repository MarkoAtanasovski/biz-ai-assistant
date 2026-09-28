package com.bizai.backend;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

/**
 * @Entity tells Spring/JPA: "this class represents a database table."
 * By default, the table will be named "sale" (lowercase class name),
 * and each field below becomes a column.
 *
 * This is the JPA equivalent of defining a MongoDB schema, or a SQL
 * CREATE TABLE statement - except we just write a plain Java class.
 */
@Entity
public class Sale {

    // @Id marks this field as the primary key.
    // @GeneratedValue means the database auto-increments it (1, 2, 3...)
    // - we never set this ourselves when creating a new Sale.
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String region;      // e.g. "Ljubljana", "Maribor"
    private String product;     // e.g. "Widget A"
    private Double revenue;     // e.g. 1250.50
    private Integer unitsSold;  // e.g. 42
    // "month" is a reserved SQL keyword in H2 (it's a built-in date
    // function). @Column lets us keep the Java field named "month" while
    // storing it under a different, safe column name in the database.
    @Column(name = "sale_month")
    private String month;       // e.g. "2026-08"

    // JPA requires a no-argument constructor - it uses this internally
    // when loading rows back out of the database.
    public Sale() {
    }

    public Sale(String region, String product, Double revenue, Integer unitsSold, String month) {
        this.region = region;
        this.product = product;
        this.revenue = revenue;
        this.unitsSold = unitsSold;
        this.month = month;
    }

    // Getters and setters: Java convention for reading/writing private
    // fields from outside the class. Spring uses these automatically
    // when converting this object to/from JSON.
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getRegion() { return region; }
    public void setRegion(String region) { this.region = region; }

    public String getProduct() { return product; }
    public void setProduct(String product) { this.product = product; }

    public Double getRevenue() { return revenue; }
    public void setRevenue(Double revenue) { this.revenue = revenue; }

    public Integer getUnitsSold() { return unitsSold; }
    public void setUnitsSold(Integer unitsSold) { this.unitsSold = unitsSold; }

    public String getMonth() { return month; }
    public void setMonth(String month) { this.month = month; }
}
