package org.example.bot;

import org.example.bot.Order;
import org.example.bot.Product;
import org.example.bot.OrderRepo;
import org.example.bot.ProductRepo;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class DataSeeder implements CommandLineRunner {

    private final ProductRepo ProductRepo;
    private final OrderRepo OrderRepo;

    public DataSeeder(ProductRepo ProductRepo, OrderRepo OrderRepo) {
        this.ProductRepo = ProductRepo;
        this.OrderRepo = OrderRepo;
    }

    @Override
    public void run(String... args) {
        ProductRepo.save(new Product("Wireless Mouse", "Electronics", 19.99, 150));
        ProductRepo.save(new Product("Mechanical Keyboard", "Electronics", 79.99, 60));
        ProductRepo.save(new Product("Yoga Mat", "Fitness", 24.99, 200));

        OrderRepo.save(new Order("Alice Smith", "SHIPPED", 99.98));
        OrderRepo.save(new Order("Bob Jones", "PENDING", 24.99));
    }
}
