from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Text, LargeBinary, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    role = Column(String(50), nullable=False, default="Viewer")  # Admin, Procurement Officer, Viewer

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    abbrev = Column(String(20), nullable=True)

    parent = relationship("Category", remote_side=[id], backref="subcategories")
    materials = relationship("Material", back_populates="category")
    harmonized_materials = relationship("HarmonizedMaterial", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name} (Code: {self.abbrev})>"

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    cpse = Column(String(50), nullable=False)
    location = Column(String(150), nullable=False)

    inventories = relationship("Inventory", back_populates="warehouse")

    def __repr__(self):
        return f"<Warehouse {self.name} - {self.cpse}>"

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    contact_info = Column(String(255), nullable=True)

    inventories = relationship("Inventory", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier {self.name}>"

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cpse = Column(String(50), nullable=False)  # Immutable for traceability
    legacy_code = Column(String(100), nullable=False)  # Immutable for traceability
    raw_description = Column(Text, nullable=False)
    normalized_description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    material_type = Column(String(100), nullable=True)
    specification = Column(String(150), nullable=True)
    dimensions_json = Column(Text, nullable=True)  # JSON string of extracted dims
    uom = Column(String(30), nullable=True)
    unit_price = Column(Float, default=0.0)
    status = Column(String(30), default="raw")  # raw, processed, mapped
    embedding_vector = Column(LargeBinary, nullable=True)  # Serialized numpy vector
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="materials")
    inventories = relationship("Inventory", back_populates="material")
    mappings = relationship("MaterialMapping", back_populates="material")

    def __repr__(self):
        return f"<Material {self.cpse}:{self.legacy_code}>"

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    available_qty = Column(Float, default=0.0)
    reserved_qty = Column(Float, default=0.0)
    on_order_qty = Column(Float, default=0.0)
    reorder_level = Column(Float, default=0.0)

    material = relationship("Material", back_populates="inventories")
    warehouse = relationship("Warehouse", back_populates="inventories")
    supplier = relationship("Supplier", back_populates="inventories")

    def __repr__(self):
        return f"<Inventory Mat:{self.material_id} Wh:{self.warehouse_id} Avail:{self.available_qty}>"

class HarmonizedMaterial(Base):
    __tablename__ = "harmonized_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    common_code = Column(String(50), unique=True, nullable=False)  # e.g., NMC-FST-0001
    standard_description = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    material_type = Column(String(100), nullable=True)
    specification = Column(String(150), nullable=True)
    dimensions_json = Column(Text, nullable=True)
    uom = Column(String(30), nullable=True)
    status = Column(String(30), default="active")  # active, archived
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="harmonized_materials")
    mappings = relationship("MaterialMapping", back_populates="harmonized_material")

    def __repr__(self):
        return f"<HarmonizedMaterial {self.common_code}>"

class MaterialMapping(Base):
    __tablename__ = "material_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    harmonized_material_id = Column(Integer, ForeignKey("harmonized_materials.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    cpse = Column(String(50), nullable=False)  # Redundant for fast audit lookup
    legacy_code = Column(String(100), nullable=False)
    mapped_at = Column(DateTime, default=datetime.utcnow)
    mapped_by = Column(String(100), default="System/Officer")

    harmonized_material = relationship("HarmonizedMaterial", back_populates="mappings")
    material = relationship("Material", back_populates="mappings")

    def __repr__(self):
        return f"<Mapping {self.cpse}:{self.legacy_code} -> {self.harmonized_material_id}>"

class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_a_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    material_b_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    semantic_score = Column(Float, default=0.0)
    material_score = Column(Float, default=0.0)
    dimension_score = Column(Float, default=0.0)
    category_score = Column(Float, default=0.0)
    specification_score = Column(Float, default=0.0)
    uom_score = Column(Float, default=0.0)
    final_confidence = Column(Float, default=0.0)
    match_type = Column(String(50), nullable=False)  # EXACT_DUPLICATE, NEAR_DUPLICATE, FUNCTIONALLY_EQUIVALENT, SIMILAR_NOT_EQUIVALENT, NO_MATCH
    explanation_text = Column(Text, nullable=False)
    status = Column(String(30), default="pending")  # pending, approved, rejected, modified
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    material_a = relationship("Material", foreign_keys=[material_a_id])
    material_b = relationship("Material", foreign_keys=[material_b_id])

    def __repr__(self):
        return f"<MatchResult {self.material_a_id} vs {self.material_b_id} ({self.match_type}: {self.final_confidence}%)>"

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AuditLog {self.timestamp.strftime('%H:%M:%S')} - {self.action} by {self.actor}>"

class MatchGroup(Base):
    __tablename__ = "match_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_min_confidence = Column(Float, default=0.0)
    group_avg_confidence = Column(Float, default=0.0)
    match_type = Column(String(50), nullable=False)  # EXACT_DUPLICATE, NEAR_DUPLICATE, FUNCTIONALLY_EQUIVALENT
    status = Column(String(30), default="pending")  # pending, approved, rejected, modified
    recommended_common_code = Column(String(50), nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    auto_approval_reason = Column(String(255), nullable=True)
    harmonized_material_id = Column(Integer, ForeignKey("harmonized_materials.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("MatchGroupMember", back_populates="group", cascade="all, delete-orphan")
    harmonized_material = relationship("HarmonizedMaterial")

    def __repr__(self):
        return f"<MatchGroup #{self.id} ({self.match_type}: Min {self.group_min_confidence:.1f}%) - {self.status}>"

class MatchGroupMember(Base):
    __tablename__ = "match_group_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("match_groups.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)

    group = relationship("MatchGroup", back_populates="members")
    material = relationship("Material")

    def __repr__(self):
        return f"<MatchGroupMember Group:{self.group_id} Mat:{self.material_id}>"

