package com.example.mcp;

import java.util.Map;

/**
 * Interface defining the contract for MCP tools
 */
public interface Tool {
    /**
     * Execute the tool operation
     * @return Result of the tool execution
     */
    Object execute();

    /**
     * Get the tool metadata
     * @return Map containing tool metadata
     */
    Map<String, Object> getMetadata();
} 