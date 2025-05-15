package com.example.service;

import com.example.model.TableDefinition;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import java.sql.ResultSet;
import java.util.List;

@Service
public class TableDefinitionService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    private final RowMapper<TableDefinition> rowMapper = (ResultSet rs, int rowNum) -> {
        TableDefinition definition = new TableDefinition();
        definition.setTableName(rs.getString("CTABLE_NAME"));
        definition.setDisplayName(rs.getString("DISPLAY_NAME"));
        definition.setColumnName(rs.getString("CCOLUMN_NAME"));
        definition.setColumnDisplayName(rs.getString("CDISPLAY_NAME"));
        definition.setDataType(rs.getString("CDATA_TYPE"));
        definition.setReferenceType(rs.getString("CREFERENCE_TYPE"));
        definition.setEnumType(rs.getString("CENUM_TYPE"));
        definition.setUnitType(rs.getString("CUNIT_TYPE"));
        definition.setClassificationType(rs.getString("CCLASSIFICATION_TYPE"));
        return definition;
    };

    public List<TableDefinition> getTableDefinitions() {
        String sql = "select t1.CTABLE_NAME, t1.CDISPLAY_NAME as DISPLAY_NAME, " +
                "t2.CCOLUMN_NAME, t2.CDISPLAY_NAME, t2.CDATA_TYPE, " +
                "t2.CREFERENCE_TYPE, t2.CENUM_TYPE, t2.CUNIT_TYPE, " +
                "t2.CCLASSIFICATION_TYPE " +
                "from MOM3_DEV.DM_TYPE_DEFINITION t1 " +
                "JOIN MOM3_DEV.DM_TYPE_DEFINITION_PROPERTY t2 " +
                "ON t1.CCODE = t2.CTYPE_ENTITY_TYPE " +
                "WHERE t1.CTABLE_NAME is not null " +
                "order by t1.CTABLE_NAME";
        
        return jdbcTemplate.query(sql, rowMapper);
    }
} 