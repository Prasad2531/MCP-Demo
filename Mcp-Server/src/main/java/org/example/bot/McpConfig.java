package org.example.bot;

import org.example.bot.EcommerceToolService;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class McpConfig {

    @Bean
    public ToolCallbackProvider ecommerceTools(EcommerceToolService toolService) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(toolService)
                .build();
    }
}
