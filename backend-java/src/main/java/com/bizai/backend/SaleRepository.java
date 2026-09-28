package com.bizai.backend;

import org.springframework.data.jpa.repository.JpaRepository;

/**
 * This interface looks almost empty, but it's doing a lot of work.
 *
 * By extending JpaRepository<Sale, Long>, we tell Spring:
 *   - "Sale" = the entity this repository manages
 *   - "Long" = the type of Sale's @Id field
 *
 * Spring then AUTO-GENERATES an implementation of this interface at
 * runtime, giving us methods like:
 *   save(sale)        -> INSERT or UPDATE a row
 *   findAll()          -> SELECT * FROM sale
 *   findById(id)        -> SELECT * FROM sale WHERE id = ?
 *   deleteById(id)      -> DELETE FROM sale WHERE id = ?
 * ...without us writing a single line of SQL or implementation code.
 *
 * This is roughly equivalent to a Mongoose Model in Node.js/MongoDB,
 * or a Django Model's default manager (Sale.objects.all(), etc.)
 * - just Java's more verbose, explicit style.
 */
public interface SaleRepository extends JpaRepository<Sale, Long> {
    // We can add custom query methods here later just by naming them
    // a certain way, e.g.:
    //   List<Sale> findByRegion(String region);
    // Spring parses the method name and builds the SQL query for us.
}
