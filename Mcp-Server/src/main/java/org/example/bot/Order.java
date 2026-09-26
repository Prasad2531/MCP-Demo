package org.example.bot;

import jakarta.persistence.*;

@Entity
@Table(name = "orders")
public class Order {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String customerName;
    private String status; // PENDING, SHIPPED, DELIVERED, CANCELLED
    private double totalAmount;

    protected Order() {}

    public Order(String customerName, String status, double totalAmount) {
        this.customerName = customerName;
        this.status = status;
        this.totalAmount = totalAmount;
    }

    public Long getId() { return id; }
    public String getCustomerName() { return customerName; }
    public String getStatus() { return status; }
    public double getTotalAmount() { return totalAmount; }
}