package org.example.bot;


import org.example.bot.Order;
import org.example.bot.Product;
import org.example.bot.OrderRepo;
import org.example.bot.ProductRepo;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class EcommerceToolService {

    private final ProductRepo ProductRepo;
    private final OrderRepo OrderRepo;

    public EcommerceToolService(ProductRepo ProductRepo, OrderRepo OrderRepo) {
        this.ProductRepo = ProductRepo;
        this.OrderRepo = OrderRepo;
    }

    @Tool(description = "Search products by name keyword")
    public List<Product> searchProducts(String query) {
        return ProductRepo.findByNameContainingIgnoreCase(query);
    }

    @Tool(description = "Check current stock quantity for a product by its ID")
    public String checkInventory(Long productId) {
        return ProductRepo.findById(productId)
                .map(p -> p.getName() + " has " + p.getStockQuantity() + " units in stock")
                .orElse("Product with ID " + productId + " not found");
    }

    @Tool(description = "Get the status and total amount of an order by order ID")
    public String getOrderStatus(Long orderId) {
        return OrderRepo.findById(orderId)
                .map(o -> "Order #" + o.getId() + " for " + o.getCustomerName() +
                        " is " + o.getStatus() + ", total $" + o.getTotalAmount())
                .orElse("Order with ID " + orderId + " not found");
    }
}
