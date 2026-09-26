package com.training.mcptestclient;

import io.modelcontextprotocol.client.McpSyncClient;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.mcp.SyncMcpToolCallbackProvider;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

import java.util.List;
import java.util.Scanner;

@SpringBootApplication
public class McpTestClientApplication {

    public static void main(String[] args) {
        SpringApplication.run(McpTestClientApplication.class, args);
    }

    @Bean
    public CommandLineRunner runner(ChatClient.Builder chatClientBuilder, List<McpSyncClient> mcpSyncClients) {
        return args -> {
            var toolCallbacks = new SyncMcpToolCallbackProvider(mcpSyncClients);

            ChatClient chatClient = chatClientBuilder
                    .defaultToolCallbacks(toolCallbacks)
                    .build();

            Scanner scanner = new Scanner(System.in);
            System.out.println("=== E-commerce Agent (Qwen2.5 + MCP tools) ===");
            System.out.println("Try: 'search for mouse' or 'what's the status of order 1'\n");

            while (true) {
                System.out.print("You: ");
                String input = scanner.nextLine();
                if (input.equalsIgnoreCase("exit")) break;

                String response = chatClient.prompt()
                        .user(input)
                        .call()
                        .content();

                System.out.println("Bot: " + response + "\n");
            }
            scanner.close();
        };
    }
}