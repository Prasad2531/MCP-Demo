package org.example.bot;


import org.example.bot.Product;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ProductRepo extends JpaRepository<Product, Long> {
    List<Product> findByNameContainingIgnoreCase(String name);
}