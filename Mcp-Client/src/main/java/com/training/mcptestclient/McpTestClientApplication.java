package com.training.mcptestclient;

import io.modelcontextprotocol.client.McpSyncClient;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

import java.util.List;
import java.util.Map;

@SpringBootApplication
public class McpTestClientApplication {

    public static void main(String[] args) {
        SpringApplication.run(McpTestClientApplication.class, args);
    }

    @Bean
    public CommandLineRunner runner(List<McpSyncClient> mcpClients) {
        return args -> {
            McpSyncClient client = mcpClients.get(0);

            System.out.println("=== Available Tools ===");
            client.listTools().tools().forEach(tool ->
                    System.out.println("- " + tool.name() + ": " + tool.description()));

            System.out.println("\n=== Calling searchProducts(query=mouse) ===");
            var result = client.callTool(new io.modelcontextprotocol.spec.McpSchema.CallToolRequest(
                    "searchProducts", Map.of("query", "mouse")));
            System.out.println(result.content());
        };
    }
}