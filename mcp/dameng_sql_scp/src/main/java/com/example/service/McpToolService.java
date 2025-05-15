package com.example.service;

import com.example.model.McpTool;
import com.example.model.McpMessage;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Service
public class McpToolService extends BaseMcpService {

    private final List<McpTool> availableTools;

    public McpToolService() {
        this.availableTools = new ArrayList<>();
        initializeTools();
    }

    private void initializeTools() {
        availableTools.add(McpTool.builder()
                .name("get_true_tables")
                .description("Get table definitions from Dameng database")
                .type("sse")
                .endpoint("/api/get_true_tables")
                .method("GET")
                .build());
        // Add more tools here as needed
    }

    public SseEmitter listTools(String clientId) {
        SseEmitter emitter = new SseEmitter();
        emitters.put(clientId, emitter);
        
        emitter.onCompletion(() -> removeClient(clientId));
        emitter.onTimeout(() -> removeClient(clientId));
        
        executorService.execute(() -> {
            try {
                McpMessage message = McpMessage.builder()
                    .type("tool_list")
                    .event("list_tools")
                    .data(availableTools)
                    .id(UUID.randomUUID().toString())
                    .timestamp(System.currentTimeMillis())
                    .build();
                emitter.send(message);
                emitter.complete();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        });
        
        return emitter;
    }

    public List<McpTool> getAvailableTools() {
        return new ArrayList<>(availableTools);
    }
} 