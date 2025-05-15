package com.example.model;

import lombok.Data;
import lombok.AllArgsConstructor;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class TableDefinition {
    private String tableName;
    private String displayName;
    private String columnName;
    private String columnDisplayName;
    private String dataType;
    private String referenceType;
    private String enumType;
    private String unitType;
    private String classificationType;
} 