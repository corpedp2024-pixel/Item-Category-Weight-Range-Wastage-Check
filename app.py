# app.py
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="File Comparison", layout="wide")
st.title("📊 Side-by-Side File Comparison")

def read_file(f):
    """Read CSV or Excel file with error handling"""
    try:
        if f.name.lower().endswith(".csv"):
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(f, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # If all encodings fail, try with default
                df = pd.read_csv(f)
        else:
            df = pd.read_excel(f)
        
        df.columns = df.columns.str.strip()
        return df.fillna("")
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return None

def safe_get_value(value):
    """Safely extract scalar value from pandas Series or array"""
    try:
        # If it's a Series with multiple values
        if hasattr(value, 'iloc'):
            if len(value) > 0:
                val = value.iloc[0]
                return "" if pd.isna(val) else str(val)
            return ""
        # If it's a numpy array
        elif hasattr(value, 'item'):
            try:
                val = value.item()
                return "" if pd.isna(val) else str(val)
            except:
                return str(value) if not pd.isna(value) else ""
        # Regular scalar value
        else:
            return "" if pd.isna(value) else str(value)
    except:
        return str(value) if value else ""

def compare_dataframes(df1, df2, mapping, required_keys):
    """Compare two dataframes based on mapping"""
    key_cols_file1 = [mapping[k][0] for k in required_keys]
    key_cols_file2 = [mapping[k][1] for k in required_keys]
    
    # Create composite keys
    df1["KEY"] = df1[key_cols_file1].astype(str).agg("|".join, axis=1)
    df2["KEY"] = df2[key_cols_file2].astype(str).agg("|".join, axis=1)
    
    # Get all columns except KEY
    allcols1 = [c for c in df1.columns if c != "KEY"]
    allcols2 = [c for c in df2.columns if c != "KEY"]
    
    # Set index and compare
    m1 = df1.set_index("KEY")
    m2 = df2.set_index("KEY")
    keys = sorted(set(m1.index).union(set(m2.index)))
    
    rows = []
    for k in keys:
        r = {}
        a = m1.loc[k] if k in m1.index else None
        b = m2.loc[k] if k in m2.index else None
        
        # Add File 1 columns
        for c in allcols1:
            r[f"F1_{c}"] = "" if a is None else a[c]
        # Add File 2 columns
        for c in allcols2:
            r[f"F2_{c}"] = "" if b is None else b[c]
        
        # Determine status
        diff = []
        if a is None:
            status = "Only in File 2"
        elif b is None:
            status = "Only in File 1"
        else:
            common_cols = set(allcols1).intersection(set(allcols2))
            for c in common_cols:
                # Skip LabourChargesRate when checking for differences
                if c == "LabourChargesRate":
                    continue
                if str(a[c]).strip() != str(b[c]).strip():
                    diff.append(c)
            status = "Different" if diff else "Same"
        
        r["Status"] = status
        r["Changed Columns"] = ", ".join(diff)
        rows.append(r)
    
    return pd.DataFrame(rows)

# Define required key columns
REQUIRED_KEYS = ["Item Name", "Item Category Name", "Purity", "FromWt", "ToWt"]

# File upload
col1, col2 = st.columns(2)
with col1:
    f1 = st.file_uploader("📁 Upload File 1", type=["xlsx","xls","csv"], key="file1")
with col2:
    f2 = st.file_uploader("📁 Upload File 2", type=["xlsx","xls","csv"], key="file2")

if f1 and f2:
    with st.spinner("Reading files..."):
        df1 = read_file(f1)
        df2 = read_file(f2)
        
        if df1 is None or df2 is None:
            st.stop()
    
    # Show column mapping
    st.subheader("🔗 Column Mapping")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**File 1 Columns:**")
        st.write(list(df1.columns))
    with col2:
        st.write("**File 2 Columns:**")
        st.write(list(df2.columns))
    
    # Create mapping for each key
    st.write("**Map columns for matching records:**")
    mapping = {}
    cols = st.columns(len(REQUIRED_KEYS))
    
    for idx, key in enumerate(REQUIRED_KEYS):
        with cols[idx]:
            st.write(f"**{key}**")
            default1 = key if key in df1.columns else ""
            default2 = key if key in df2.columns else ""
            
            col1_map = st.selectbox(
                f"File 1",
                options=[""] + list(df1.columns),
                index=0 if default1 == "" else list(df1.columns).index(default1) + 1,
                key=f"map1_{idx}"
            )
            col2_map = st.selectbox(
                f"File 2",
                options=[""] + list(df2.columns),
                index=0 if default2 == "" else list(df2.columns).index(default2) + 1,
                key=f"map2_{idx}"
            )
            mapping[key] = (col1_map, col2_map)
    
    # Validate mappings
    missing_mappings = []
    for key, (c1, c2) in mapping.items():
        if not c1:
            missing_mappings.append(f"File 1 - {key}")
        if not c2:
            missing_mappings.append(f"File 2 - {key}")
    
    if missing_mappings:
        st.error(f"⚠️ Please map all columns. Missing: {', '.join(missing_mappings)}")
        st.stop()
    
    # Perform comparison
    with st.spinner("Comparing files..."):
        out = compare_dataframes(df1, df2, mapping, REQUIRED_KEYS)
    
    # Display summary
    st.subheader("📊 Comparison Summary")
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Total Records", len(out))
    with summary_cols[1]:
        st.metric("Only in File 1", len(out[out["Status"] == "Only in File 1"]))
    with summary_cols[2]:
        st.metric("Only in File 2", len(out[out["Status"] == "Only in File 2"]))
    with summary_cols[3]:
        st.metric("Different", len(out[out["Status"] == "Different"]))
    
    # Display results
    st.subheader("📋 Comparison Results")
    st.dataframe(out, use_container_width=True, height=400)
    
    # Filter options
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=out["Status"].unique(),
            default=out["Status"].unique()
        )
    
    filtered_out = out[out["Status"].isin(status_filter)]
    st.dataframe(filtered_out, use_container_width=True)
    
    # Export options
    st.subheader("💾 Export Results")
    
    # Excel export with formatting
    excel = BytesIO()
    with pd.ExcelWriter(excel, engine="xlsxwriter") as writer:
        filtered_out.to_excel(writer, index=False, sheet_name="Comparison")
        wb = writer.book
        ws = writer.sheets["Comparison"]
        
        # Formats
        red = wb.add_format({"bg_color": "#FFC7CE"})
        green = wb.add_format({"bg_color": "#C6EFCE"})
        yellow = wb.add_format({"bg_color": "#FFEB9C"})
        head = wb.add_format({"bold": True, "bg_color": "#D9EAD3", "border": 1})
        
        # Write headers and set column widths
        for c, col in enumerate(filtered_out.columns):
            ws.write(0, c, col, head)
            ws.set_column(c, c, max(14, len(col) + 2))
        
        # Apply formatting with safe value extraction
        for i, row in filtered_out.iterrows():
            row_num = i + 1
            status = row["Status"]
            
            if status == "Different":
                # Format different rows
                changed_cols = row["Changed Columns"].split(", ")
                for col in changed_cols:
                    if col:
                        # Skip LabourChargesRate column - don't highlight it
                        if col == "LabourChargesRate":
                            continue
                        c1_key = f"F1_{col}"
                        c2_key = f"F2_{col}"
                        if c1_key in filtered_out.columns:
                            c1_idx = filtered_out.columns.get_loc(c1_key)
                            value = safe_get_value(row[c1_key])
                            ws.write(row_num, c1_idx, value, red)
                        if c2_key in filtered_out.columns:
                            c2_idx = filtered_out.columns.get_loc(c2_key)
                            value = safe_get_value(row[c2_key])
                            ws.write(row_num, c2_idx, value, red)
            elif status == "Only in File 1":
                # Highlight rows only in file 1
                for c in range(len(filtered_out.columns)):
                    value = safe_get_value(row.iloc[c])
                    ws.write(row_num, c, value, yellow)
            elif status == "Only in File 2":
                # Highlight rows only in file 2
                for c in range(len(filtered_out.columns)):
                    value = safe_get_value(row.iloc[c])
                    ws.write(row_num, c, value, green)
    
    export_cols = st.columns(3)
    with export_cols[0]:
        st.download_button(
            "📥 Download Excel",
            excel.getvalue(),
            "Comparison.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with export_cols[1]:
        st.download_button(
            "📥 Download CSV",
            filtered_out.to_csv(index=False).encode(),
            "Comparison.csv",
            "text/csv"
        )
    with export_cols[2]:
        st.download_button(
            "📥 Download JSON",
            filtered_out.to_json(orient="records").encode(),
            "Comparison.json",
            "application/json"
        )
    
    # Show column mapping for reference
    with st.expander("📖 Column Mapping Reference"):
        mapping_df = pd.DataFrame([
            {"Key Field": k, "File 1 Column": mapping[k][0], "File 2 Column": mapping[k][1]}
            for k in REQUIRED_KEYS
        ])
        st.dataframe(mapping_df, use_container_width=True)

else:
    st.info("👈 Please upload two files to begin comparison")
    
    # Show instructions
    with st.expander("ℹ️ Instructions"):
        st.markdown("""
        ### How to use this app:
        1. Upload two files (CSV or Excel) using the upload buttons
        2. Map the key columns for matching records
        3. View the comparison results
        4. Export results in various formats
        
        ### Key Fields:
        - **Item Name**: Product or item identifier
        - **Item Category Name**: Category of the item
        - **Purity**: Quality indicator
        - **FromWt**: Starting weight/quantity
        - **ToWt**: Ending weight/quantity
        
        ### Color Coding in Excel Export:
        - 🟥 **Red**: Different values between the two files (except LabourChargesRate)
        - 🟩 **Green**: Records only in File 2
        - 🟨 **Yellow**: Records only in File 1
        
        ### Features:
        - 🔍 **Column Mapping**: Map columns from both files for comparison
        - 📊 **Summary Statistics**: Quick overview of differences
        - 🎯 **Filtering**: Filter results by status
        - 💾 **Multiple Export Formats**: Excel (with formatting), CSV, JSON
        """)