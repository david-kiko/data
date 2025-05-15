package com.example.mcp;

import org.springframework.jdbc.core.JdbcTemplate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Tool for retrieving table definitions from Dameng database
 */
public class GetTrueTablesTool implements Tool {
    private final JdbcTemplate jdbcTemplate;
    private static final String QUERY = "SELECT TABLE_NAME, COMMENTS FROM DBA_TAB_COMMENTS WHERE OWNER = 'SYSDBA'";

    public GetTrueTablesTool(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public Object execute() {
        return jdbcTemplate.queryForList(QUERY);
    }

    @Override
    public Map<String, Object> getMetadata() {
        Map<String, Object> metadata = new HashMap<>();
        metadata.put("name", "get_true_tables");
        metadata.put("description", "Retrieves table definitions from Dameng database");
        metadata.put("type", "query");
        metadata.put("parameters", new HashMap<>());
        return metadata;
    }
} 