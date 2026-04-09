#!/usr/bin/env python3
"""
nebraska_runtime.py — Nebraska Generative System v2.x Runtime

Full implementation of the 7-axis narrative validation pipeline.
Author: Shaun O'Sullivan
Version: 1.0
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple, Callable
from enum import Enum
from datetime import datetime
import re

# ============================================================================
# DATA MODELS
# ============================================================================

class ComponentType(Enum):
    """Types of narrative components"""
    CHARACTER = "character"
    EVENT = "event"
    OBJECT = "object"
    SETTING = "setting"
    THEME = "theme"
    CONFLICT = "conflict"
    RESOLUTION = "resolution"

class ValidityState(Enum):
    """Component validity states through the axis pipeline"""
    UNVALIDATED = "unvalidated"
    X_AXIS_PASS = "x_axis_pass"  # Generated, not validated
    Y_AXIS_PASS = "y_axis_pass"  # Primary X→Y validation passed
    Y2_AXIS_PASS = "y2_axis_pass"  # Second-order validation passed
    Y3_AXIS_PASS = "y3_axis_pass"  # Integration validation passed
    Z_AXIS_PASS = "z_axis_pass"  # Meta-evaluation passed
    INVERSION_PASS = "inversion_pass"  # Adversarial validation passed
    REJECTED = "rejected"
    DELETED = "deleted"  # Failed final checksum

@dataclass
class Axiom:
    """The governing law of the narrative universe"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    statement: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    validated: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "statement": self.statement,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "validated": self.validated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Axiom':
        axiom = cls()
        axiom.id = data.get('id', str(uuid.uuid4())[:8])
        axiom.statement = data.get('statement', '')
        axiom.description = data.get('description', '')
        if 'created_at' in data:
            axiom.created_at = datetime.fromisoformat(data['created_at'])
        axiom.validated = data.get('validated', False)
        return axiom

@dataclass
class NarrativeComponent:
    """A single component in the narrative system"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    component_type: ComponentType = ComponentType.CHARACTER
    description: str = ""

    # Core NEBRASKA fields
    deficit_state: str = ""  # X - The problem/uncertainty
    resolution_state: str = ""  # Y - The solution/necessity
    conversion_logic: str = ""  # How X→Y under Axiom

    # Validation tracking
    validity_state: ValidityState = ValidityState.UNVALIDATED
    validation_notes: List[str] = field(default_factory=list)
    validation_failures: List[str] = field(default_factory=list)

    # Integration data
    depends_on: List[str] = field(default_factory=list)  # Component IDs
    enables: List[str] = field(default_factory=list)  # Component IDs

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_validated: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "component_type": self.component_type.value,
            "description": self.description,
            "deficit_state": self.deficit_state,
            "resolution_state": self.resolution_state,
            "conversion_logic": self.conversion_logic,
            "validity_state": self.validity_state.value,
            "validation_notes": self.validation_notes,
            "validation_failures": self.validation_failures,
            "depends_on": self.depends_on,
            "enables": self.enables,
            "created_at": self.created_at.isoformat(),
            "last_validated": self.last_validated.isoformat() if self.last_validated else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'NarrativeComponent':
        component = cls()
        component.id = data.get('id', str(uuid.uuid4())[:8])
        component.name = data.get('name', '')
        component.component_type = ComponentType(data.get('component_type', 'character'))
        component.description = data.get('description', '')
        component.deficit_state = data.get('deficit_state', '')
        component.resolution_state = data.get('resolution_state', '')
        component.conversion_logic = data.get('conversion_logic', '')
        component.validity_state = ValidityState(data.get('validity_state', 'unvalidated'))
        component.validation_notes = data.get('validation_notes', [])
        component.validation_failures = data.get('validation_failures', [])
        component.depends_on = data.get('depends_on', [])
        component.enables = data.get('enables', [])
        if 'created_at' in data:
            component.created_at = datetime.fromisoformat(data['created_at'])
        if 'last_validated' in data and data['last_validated']:
            component.last_validated = datetime.fromisoformat(data['last_validated'])
        return component

    def get_conversion_summary(self) -> str:
        """Generate the X→Y conversion statement"""
        if self.deficit_state and self.resolution_state:
            return f"Converts '{self.deficit_state}' to '{self.resolution_state}'"
        return "No conversion defined"

    def is_valid(self) -> bool:
        """Check if component has passed validation"""
        valid_states = [
            ValidityState.Y_AXIS_PASS,
            ValidityState.Y2_AXIS_PASS,
            ValidityState.Y3_AXIS_PASS,
            ValidityState.Z_AXIS_PASS,
            ValidityState.INVERSION_PASS
        ]
        return self.validity_state in valid_states

# ============================================================================
# VALIDATION AXES
# ============================================================================

class BaseAxisValidator:
    """Base class for axis validators"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:
        """Validate a component against this axis"""
        raise NotImplementedError

    def __str__(self):
        return f"AxisValidator({self.name})"


class XAxisValidator(BaseAxisValidator):
    """X-Axis: Entropy Input/Generation Layer"""

    def __init__(self):
        super().__init__("X-Axis", "Entropy Input - Generative layer")

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:
        # X-axis doesn't reject, just marks as generated
        notes = ["Generated in X-axis expansion phase"]
        component.validity_state = ValidityState.X_AXIS_PASS
        component.validation_notes.extend(notes)
        component.last_validated = datetime.now()
        return True, notes


class YAxisValidator(BaseAxisValidator):
    """Y-Axis: Primary Structural Filter (X→Y under Axiom)"""

    def __init__(self, strict_mode: bool = True):
        super().__init__("Y-Axis", "Primary validity constraint - X→Y under Axiom")
        self.strict_mode = strict_mode

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:
        failures = []
        notes = []

        # Check 1: X must be defined
        if not component.deficit_state.strip():
            failures.append("X (deficit state) is undefined or empty")

        # Check 2: Y must be defined
        if not component.resolution_state.strip():
            failures.append("Y (resolution state) is undefined or empty")

        # Check 3: Conversion logic must reference the Axiom
        if not component.conversion_logic.strip():
            failures.append("Conversion logic is undefined")
        elif axiom.statement and axiom.statement.lower() not in component.conversion_logic.lower():
            if self.strict_mode:
                failures.append(f"Conversion logic does not reference the Axiom: '{axiom.statement}'")
            else:
                notes.append(f"Conversion logic weakly references Axiom")

        # Check 4: X and Y must be different (conversion must occur)
        if component.deficit_state and component.resolution_state:
            if component.deficit_state.strip().lower() == component.resolution_state.strip().lower():
                failures.append("X and Y are identical - no conversion occurs")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.REJECTED
            component.last_validated = datetime.now()
            return False, failures

        # Pass
        component.validity_state = ValidityState.Y_AXIS_PASS
        component.validation_notes.append(f"Passed Y-Axis: {component.get_conversion_summary()}")
        component.last_validated = datetime.now()
        notes.append(f"Valid conversion under axiom: {component.get_conversion_summary()}")
        return True, notes


class Y2AxisValidator(BaseAxisValidator):
    """Y²-Axis: Second-Order Validity (Clarity and Necessity)"""

    def __init__(self):
        super().__init__("Y²-Axis", "Second-order validity - clarity and necessity check")

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:

        # Component must have passed Y-Axis first
        if component.validity_state != ValidityState.Y_AXIS_PASS:
            return False, [f"Cannot validate Y² without Y-Axis pass. Current: {component.validity_state}"]

        failures = []
        notes = []

        # Check 1: X must be specific, not vague
        vague_indicators = ["some", "various", "certain", "multiple", "different", "general", "overall"]
        x_lower = component.deficit_state.lower()
        for vague in vague_indicators:
            if vague in x_lower and len(component.deficit_state.split()) < 4:
                failures.append(f"X is too vague: '{component.deficit_state}'")
                break

        # Check 2: Y must logically follow from X
        # This is a heuristic check - we look for logical connectives
        if component.conversion_logic:
            logic = component.conversion_logic.lower()
            if "because" not in logic and "therefore" not in logic and "thus" not in logic:
                notes.append("Conversion logic lacks explicit causal connective (because, therefore, thus)")

            # Check for weasel words
            weasel_words = ["might", "could", "possibly", "perhaps", "maybe", "somehow"]
            for word in weasel_words:
                if word in logic:
                    failures.append(f"Conversion logic contains weasel word: '{word}'")

        # Check 3: Conversion must be non-trivial
        x_words = len(component.deficit_state.split())
        y_words = len(component.resolution_state.split())
        if x_words < 2 or y_words < 2:
            failures.append("X or Y is too simplistic (needs more specific definition)")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.REJECTED
            component.last_validated = datetime.now()
            return False, failures

        # Pass
        component.validity_state = ValidityState.Y2_AXIS_PASS
        component.validation_notes.append(f"Passed Y²-Axis: Clear and necessary conversion")
        component.last_validated = datetime.now()
        notes.append("Conversion is clear, specific, and logically necessary")
        return True, notes


class Y3AxisValidator(BaseAxisValidator):
    """Y³-Axis: Integration Validity (Systemic Coherence)"""

    def __init__(self):
        super().__init__("Y³-Axis", "Integration validity - systemic coherence check")

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:

        # Component must have passed Y²-Axis first
        if component.validity_state != ValidityState.Y2_AXIS_PASS:
            return False, [f"Cannot validate Y³ without Y²-Axis pass. Current: {component.validity_state}"]

        failures = []
        notes = []

        # Get all valid components in the narrative
        valid_components = narrative_state.get_valid_components()

        # Check 1: Component should connect to other components
        connections = 0

        # Check dependencies
        for dep_id in component.depends_on:
            dep_component = narrative_state.get_component(dep_id)
            if dep_component and dep_component.is_valid():
                connections += 1
                notes.append(f"Depends on valid component: {dep_component.name}")
            elif dep_component:
                failures.append(f"Depends on invalid component: {dep_component.name}")
            else:
                failures.append(f"Depends on non-existent component ID: {dep_id}")

        # Check what this component enables
        for enabled_id in component.enables:
            enabled_component = narrative_state.get_component(enabled_id)
            if enabled_component:
                connections += 1
                notes.append(f"Enables component: {enabled_component.name}")
            else:
                notes.append(f"Enables future component ID: {enabled_id}")

        # If no connections at all, it might be an island
        if connections == 0 and len(valid_components) > 1:
            failures.append("Component is isolated - no connections to other valid components")

        # Check 2: Component's Y should not contradict other components' X or Y
        for other in valid_components:
            if other.id == component.id:
                continue

            # Check if component's resolution contradicts another's deficit
            if (component.resolution_state and other.deficit_state and
                "not " + component.resolution_state.lower() in other.deficit_state.lower()):
                failures.append(f"Resolution contradicts {other.name}'s deficit: {other.deficit_state}")

            # Check if two components solve the same deficit (redundancy)
            if (component.deficit_state and other.deficit_state and
                component.deficit_state.lower() == other.deficit_state.lower() and
                component.resolution_state.lower() == other.resolution_state.lower()):
                failures.append(f"Redundant with {other.name} - solves same deficit")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.REJECTED
            component.last_validated = datetime.now()
            return False, failures

        # Pass
        component.validity_state = ValidityState.Y3_AXIS_PASS
        component.validation_notes.append(f"Passed Y³-Axis: Integrated into narrative system")
        component.last_validated = datetime.now()
        notes.append(f"Component integrates with {connections} other component(s)")
        return True, notes


class ZAxisValidator(BaseAxisValidator):
    """Z-Axis: Meta-Evaluation (Axiomatic Consistency)"""

    def __init__(self):
        super().__init__("Z-Axis", "Meta-evaluation - axiomatic consistency")

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:

        # Component must have passed Y³-Axis first
        if component.validity_state != ValidityState.Y3_AXIS_PASS:
            return False, [f"Cannot validate Z-Axis without Y³-Axis pass. Current: {component.validity_state}"]

        failures = []
        notes = []

        # Check 1: Component's existence should be implied by the Axiom
        if axiom.statement:
            # Heuristic: component should reference concepts from axiom
            axiom_words = set(axiom.statement.lower().split())
            component_text = f"{component.name} {component.description} {component.deficit_state} {component.resolution_state}".lower()
            component_words = set(component_text.split())

            overlapping = axiom_words.intersection(component_words)
            if len(overlapping) == 0:
                failures.append("Component doesn't reference any concepts from the Axiom")
            else:
                notes.append(f"Shares {len(overlapping)} concept(s) with Axiom: {', '.join(overlapping)}")

        # Check 2: Component should move narrative state forward irreversibly
        # This is checked by ensuring Y is not a regression of X
        if component.deficit_state and component.resolution_state:
            # Simple heuristic: resolution should not reintroduce the deficit
            if component.deficit_state.lower() in component.resolution_state.lower():
                failures.append("Resolution reintroduces or perpetuates the deficit")

        # Check 3: Component should test or prove the Axiom
        if component.conversion_logic:
            if "proves" not in component.conversion_logic.lower() and "tests" not in component.conversion_logic.lower():
                notes.append("Conversion doesn't explicitly test/prove the Axiom (minor note)")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.REJECTED
            component.last_validated = datetime.now()
            return False, failures

        # Pass
        component.validity_state = ValidityState.Z_AXIS_PASS
        component.validation_notes.append(f"Passed Z-Axis: Axiomatically consistent")
        component.last_validated = datetime.now()
        return True, notes


class InversionValidator(BaseAxisValidator):
    """Z-Axis Inversion: Adversarial Validation"""

    def __init__(self, narrative_state: 'NarrativeState'):
        super().__init__("Inversion", "Adversarial validation - perspective reversal")
        self.narrative_state = narrative_state

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:

        # Component must have passed Z-Axis first
        if component.validity_state != ValidityState.Z_AXIS_PASS:
            return False, [f"Cannot validate Inversion without Z-Axis pass. Current: {component.validity_state}"]

        failures = []
        notes = []

        # Test 1: Ablation test - can narrative function without this component?
        # Simulate by checking if other components depend on this one
        dependent_count = 0
        for other in narrative_state.components.values():
            if other.id != component.id and component.id in other.depends_on and other.is_valid():
                dependent_count += 1

        if dependent_count == 0:
            # No other valid components depend on this one
            # Check if this component enables anything critical
            enabling_critical = False
            for enabled_id in component.enables:
                enabled = narrative_state.get_component(enabled_id)
                if enabled and enabled.is_valid():
                    enabling_critical = True
                    break

            if not enabling_critical:
                failures.append("Ablation test: Component appears non-essential - nothing depends on it")
            else:
                notes.append(f"Component enables {len(component.enables)} other component(s)")

        # Test 2: Perspective reversal - invert X and Y
        original_x = component.deficit_state
        original_y = component.resolution_state

        # Check if inversion would make more sense (indicates weak original logic)
        if original_x and original_y:
            # Heuristic: if Y sounds like a problem and X sounds like a solution
            problem_words = ["lack", "missing", "without", "need", "want", "desire", "fear", "danger"]
            solution_words = ["have", "gain", "achieve", "resolve", "solve", "fix", "secure", "safety"]

            x_problem_score = sum(1 for word in problem_words if word in original_x.lower())
            y_solution_score = sum(1 for word in solution_words if word in original_y.lower())

            if x_problem_score < y_solution_score:
                notes.append("Inversion test: X→Y direction might be weak (Y sounds more like a solution than X sounds like a problem)")

        # Test 3: Check for false supports - does component actually deliver its Y?
        # This is a content check that's hard to automate fully
        if component.resolution_state:
            if "by" in component.conversion_logic or "through" in component.conversion_logic:
                # Has some mechanism described
                pass
            else:
                notes.append("Inversion test: Conversion mechanism not clearly described")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.REJECTED
            component.last_validated = datetime.now()
            return False, failures

        # Pass
        component.validity_state = ValidityState.INVERSION_PASS
        component.validation_notes.append(f"Passed Inversion: Adversarially robust")
        component.last_validated = datetime.now()
        return True, notes


class ChecksumValidator:
    """Final Checksum: Comprehensive Integrity Verification"""

    def __init__(self):
        self.name = "Checksum"
        self.description = "Final integrity verification - explicit X→Y proof"

    def validate(self, component: NarrativeComponent, axiom: Axiom,
                narrative_state: 'NarrativeState') -> Tuple[bool, List[str]]:

        # Component must have passed all previous validations
        if component.validity_state != ValidityState.INVERSION_PASS:
            return False, [f"Cannot finalize without passing all axes. Current: {component.validity_state}"]

        failures = []
        notes = []

        # Final explicit proof requirement
        proof_statement = f"{component.name}: X='{component.deficit_state}' → Y='{component.resolution_state}' under Axiom: '{axiom.statement}'"

        # Check 1: All fields must be populated
        required_fields = [
            ("name", component.name),
            ("deficit_state", component.deficit_state),
            ("resolution_state", component.resolution_state),
            ("conversion_logic", component.conversion_logic)
        ]

        for field_name, value in required_fields:
            if not value or not value.strip():
                failures.append(f"Final check: {field_name} is empty")

        # Check 2: Generate final proof statement
        if component.deficit_state and component.resolution_state and axiom.statement:
            proof_statement = f"{component.name} converts '{component.deficit_state}' to '{component.resolution_state}' under the law: '{axiom.statement}'"
            notes.append(f"Final proof: {proof_statement}")

        # Check 3: Ensure no remaining validation failures
        if component.validation_failures:
            failures.append(f"Final check: Component still has {len(component.validation_failures)} unresolved validation failure(s)")

        if failures:
            component.validation_failures.extend(failures)
            component.validity_state = ValidityState.DELETED
            component.last_validated = datetime.now()
            return False, failures

        # Final pass - component is fully validated
        notes.append(f"✓ Component fully validated and structurally necessary")
        component.validation_notes.append(f"Passed Final Checksum: {proof_statement}")
        component.last_validated = datetime.now()
        return True, notes


# ============================================================================
# NARRATIVE STATE & PIPELINE
# ============================================================================

class NarrativeState:
    """Main container for narrative state and components"""

    def __init__(self, axiom: Optional[Axiom] = None):
        self.axiom = axiom or Axiom()
        self.components: Dict[str, NarrativeComponent] = {}
        self.validators: List[BaseAxisValidator] = []
        self.axis_intervention_active = True
        self.validation_history: List[Dict] = []

        # Initialize with default validators
        self._initialize_default_validators()

    def _initialize_default_validators(self):
        """Set up the default axis validators"""
        self.validators = [
            XAxisValidator(),
            YAxisValidator(strict_mode=True),
            Y2AxisValidator(),
            Y3AxisValidator(),
            ZAxisValidator(),
            InversionValidator(self)
        ]
        self.checksum = ChecksumValidator()

    def add_component(self, component: NarrativeComponent) -> str:
        """Add a component to the narrative state"""
        self.components[component.id] = component
        return component.id

    def get_component(self, component_id: str) -> Optional[NarrativeComponent]:
        """Get component by ID"""
        return self.components.get(component_id)

    def get_valid_components(self) -> List[NarrativeComponent]:
        """Get all components that have passed validation"""
        return [c for c in self.components.values() if c.is_valid()]

    def get_rejected_components(self) -> List[NarrativeComponent]:
        """Get all rejected components"""
        return [c for c in self.components.values() if c.validity_state == ValidityState.REJECTED]

    def validate_pipeline(self, component_id: str, stop_on_failure: bool = True) -> Dict:
        """Run a component through the entire validation pipeline"""
        component = self.get_component(component_id)
        if not component:
            return {"success": False, "error": f"Component {component_id} not found"}

        results = {
            "component_id": component_id,
            "component_name": component.name,
            "axiom": self.axiom.statement,
            "stages": [],
            "final_state": None,
            "success": False
        }

        # Run through each axis validator
        for i, validator in enumerate(self.validators):
            stage_result = {
                "axis": validator.name,
                "description": validator.description,
                "success": False,
                "notes": [],
                "timestamp": datetime.now().isoformat()
            }

            try:
                success, notes = validator.validate(component, self.axiom, self)
                stage_result["success"] = success
                stage_result["notes"] = notes

                if not success and stop_on_failure:
                    results["stages"].append(stage_result)
                    results["final_state"] = component.validity_state.value
                    results["success"] = False

                    # Log intervention if active
                    if self.axis_intervention_active:
                        intervention_note = f"AXIS INTERVENTION: Halted at {validator.name} - {notes}"
                        component.validation_notes.append(intervention_note)
                        stage_result["notes"].append(intervention_note)

                    return results

            except Exception as e:
                stage_result["success"] = False
                stage_result["notes"] = [f"Validation error: {str(e)}"]
                component.validation_failures.append(f"Validator {validator.name} error: {e}")

                if stop_on_failure:
                    results["stages"].append(stage_result)
                    results["final_state"] = component.validity_state.value
                    results["success"] = False
                    return results

            results["stages"].append(stage_result)

        # Final checksum
        if component.is_valid():
            checksum_result = {
                "axis": self.checksum.name,
                "description": self.checksum.description,
                "success": False,
                "notes": [],
                "timestamp": datetime.now().isoformat()
            }

            try:
                success, notes = self.checksum.validate(component, self.axiom, self)
                checksum_result["success"] = success
                checksum_result["notes"] = notes

                if not success:
                    results["stages"].append(checksum_result)
                    results["final_state"] = component.validity_state.value
                    results["success"] = False
                    return results

            except Exception as e:
                checksum_result["success"] = False
                checksum_result["notes"] = [f"Checksum error: {str(e)}"]
                component.validation_failures.append(f"Checksum error: {e}")
                results["stages"].append(checksum_result)
                results["final_state"] = component.validity_state.value
                results["success"] = False
                return results

            results["stages"].append(checksum_result)

        results["final_state"] = component.validity_state.value
        results["success"] = component.is_valid() or component.validity_state == ValidityState.INVERSION_PASS

        # Add to history
        self.validation_history.append({
            "timestamp": datetime.now().isoformat(),
            "component_id": component_id,
            "success": results["success"],
            "final_state": results["final_state"]
        })

        return results

    def validate_all_components(self, batch_size: int = 10) -> Dict:
        """Validate all components in the narrative state"""
        results = {
            "total": len(self.components),
            "valid": 0,
            "rejected": 0,
            "unvalidated": 0,
            "component_results": {},
            "narrative_coherence_score": 0.0
        }

        for component_id, component in self.components.items():
            result = self.validate_pipeline(component_id, stop_on_failure=True)
            results["component_results"][component_id] = result

            if component.is_valid():
                results["valid"] += 1
            elif component.validity_state == ValidityState.REJECTED:
                results["rejected"] += 1
            else:
                results["unvalidated"] += 1

        # Calculate narrative coherence score
        valid_components = self.get_valid_components()
        if valid_components:
            # Count connections between valid components
            total_connections = 0
            for component in valid_components:
                total_connections += len([dep for dep in component.depends_on if self.get_component(dep) and self.get_component(dep).is_valid()])
                total_connections += len([en for en in component.enables if self.get_component(en) and self.get_component(en).is_valid()])

            max_possible = len(valid_components) * (len(valid_components) - 1)
            if max_possible > 0:
                results["narrative_coherence_score"] = total_connections / max_possible
            else:
                results["narrative_coherence_score"] = 1.0 if len(valid_components) == 1 else 0.0

        return results

    def generate_component_from_template(self, component_type: ComponentType,
                                       name: str, description: str) -> NarrativeComponent:
        """Generate a new component with template structure"""
        component = NarrativeComponent()
        component.name = name
        component.component_type = component_type
        component.description = description

        # Template prompts based on component type
        if component_type == ComponentType.CHARACTER:
            component.deficit_state = f"[What does {name} lack or struggle with?]"
            component.resolution_state = f"[What value does {name} provide or achieve?]"
        elif component_type == ComponentType.EVENT:
            component.deficit_state = f"[What instability or problem triggers this event?]"
            component.resolution_state = f"[What new state or understanding results?]"
        elif component_type == ComponentType.CONFLICT:
            component.deficit_state = f"[What opposing forces or needs create tension?]"
            component.resolution_state = f"[What resolution or synthesis emerges?]"
        else:
            component.deficit_state = f"[What problem or gap exists?]"
            component.resolution_state = f"[What solution or fulfillment occurs?]"

        component.conversion_logic = f"[How does this convert the deficit to resolution under axiom: '{self.axiom.statement}'?]"

        return component

    def analyze_narrative_gaps(self) -> List[Dict]:
        """Analyze the narrative for missing components or unresolved deficits"""
        gaps = []
        valid_components = self.get_valid_components()

        # Check for unresolved deficits
        all_resolutions = set()
        all_deficits = set()

        for component in valid_components:
            if component.resolution_state:
                all_resolutions.add(component.resolution_state.lower())
            if component.deficit_state:
                all_deficits.add(component.deficit_state.lower())

        # Deficits that aren't resolved by any component
        unresolved = all_deficits - all_resolutions
        for deficit in unresolved:
            # Find which component has this deficit
            for component in valid_components:
                if component.deficit_state and component.deficit_state.lower() == deficit:
                    gaps.append({
                        "type": "unresolved_deficit",
                        "component_id": component.id,
                        "component_name": component.name,
                        "deficit": component.deficit_state,
                        "description": f"Component '{component.name}' has deficit '{component.deficit_state}' but no component resolves it"
                    })

        # Check for components that don't enable anything (dead ends)
        for component in valid_components:
            if not component.enables:
                # Check if any other component depends on this one
                dependent_count = 0
                for other in valid_components:
                    if other.id != component.id and component.id in other.depends_on:
                        dependent_count += 1

                if dependent_count == 0:
                    gaps.append({
                        "type": "dead_end",
                        "component_id": component.id,
                        "component_name": component.name,
                        "description": f"Component '{component.name}' doesn't enable any other components"
                    })

        # Check for cycles in dependencies
        # Simple cycle detection
        visited = set()

        def has_cycle(comp_id, path):
            if comp_id in path:
                return True, path + [comp_id]
            if comp_id in visited:
                return False, []

            visited.add(comp_id)
            component = self.get_component(comp_id)
            if not component:
                return False, []

            for dep_id in component.depends_on:
                cycle_found, cycle_path = has_cycle(dep_id, path + [comp_id])
                if cycle_found:
                    return True, cycle_path

            return False, []

        for component in valid_components:
            cycle_found, cycle_path = has_cycle(component.id, [])
            if cycle_found and len(cycle_path) > 1:
                cycle_names = [self.get_component(cid).name for cid in cycle_path if self.get_component(cid)]
                gaps.append({
                    "type": "dependency_cycle",
                    "components": cycle_names,
                    "description": f"Circular dependency detected: {' → '.join(cycle_names)}"
                })

        return gaps

    def to_dict(self) -> Dict:
        """Serialize narrative state to dict"""
        return {
            "axiom": self.axiom.to_dict(),
            "components": {cid: comp.to_dict() for cid, comp in self.components.items()},
            "validation_history": self.validation_history,
            "settings": {
                "axis_intervention_active": self.axis_intervention_active
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'NarrativeState':
        """Deserialize narrative state from dict"""
        state = cls()
        if 'axiom' in data:
            state.axiom = Axiom.from_dict(data['axiom'])

        if 'components' in data:
            for cid, comp_data in data['components'].items():
                component = NarrativeComponent.from_dict(comp_data)
                state.components[cid] = component

        if 'validation_history' in data:
            state.validation_history = data['validation_history']

        if 'settings' in data:
            state.axis_intervention_active = data['settings'].get('axis_intervention_active', True)

        return state

    def save_to_file(self, filename: str):
        """Save narrative state to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filename: str) -> 'NarrativeState':
        """Load narrative state from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)


# ============================================================================
# PROMPT ENGINE FOR LLM INTEGRATION
# ============================================================================

class NebraskaPromptEngine:
    """Generate structured prompts for LLMs based on Nebraska framework"""

    @staticmethod
    def generate_axiom_extraction_prompt(story_concept: str) -> str:
        """Generate prompt to extract Axiom from story concept"""
        return f"""Given this story concept: "{story_concept}"

Extract the governing law or core principle (Axiom) that will drive the narrative.
The Axiom should be a testable statement that defines the story's "physics".

Format your response as:
AXIOM: [Your single-sentence axiom statement]
RATIONALE: [Brief explanation of why this is the governing law]

Example:
Concept: "A detective investigates a haunted house"
AXIOM: "Hauntings require an architect"
RATIONALE: Every supernatural occurrence must have a human cause or creator."""

    @staticmethod
    def generate_component_validation_prompt(component: Dict, axiom: str) -> str:
        """Generate prompt to validate/refine a narrative component"""
        return f"""Validate this narrative component against the Axiom: "{axiom}"

COMPONENT:
- Name: {component.get('name', 'Unnamed')}
- Type: {component.get('type', 'Unknown')}
- Description: {component.get('description', 'No description')}
- Current X (Deficit): {component.get('deficit_state', 'Not defined')}
- Current Y (Resolution): {component.get('resolution_state', 'Not defined')}

NEBRASKA VALIDATION:
1. Does this component convert a specific deficit (X) to a specific resolution (Y)?
2. Does this conversion serve or test the Axiom: "{axiom}"?
3. Is the X→Y conversion clear, logical, and necessary?

If valid, provide:
VALIDATED_X: [Improved/corrected deficit statement]
VALIDATED_Y: [Improved/corrected resolution statement]
CONVERSION_LOGIC: [How X→Y under the Axiom]
VALIDATION_SCORE: [1-10, where 10 is perfectly valid]

If invalid, provide:
REJECTION_REASON: [Why it fails validation]
SUGGESTED_FIX: [How to make it valid, or "DELETE" if unrecoverable]"""

    @staticmethod
    def generate_component_generation_prompt(axiom: str, component_type: str,
                                           context: str = "") -> str:
        """Generate prompt to create new components under an Axiom"""
        return f"""Generate a narrative component of type "{component_type}" that operates under this Axiom: "{axiom}"

{context}

The component must:
1. Address a specific deficit (problem, lack, or need) - this is X
2. Provide a specific resolution (solution, value, or outcome) - this is Y
3. Demonstrate how X converts to Y in service of or in challenge to the Axiom

Provide:
NAME: [Component name]
TYPE: [{component_type}]
DESCRIPTION: [Brief description]
X (DEFICIT): [The specific problem addressed]
Y (RESOLUTION): [The specific value provided]
CONVERSION_LOGIC: [How X→Y under the Axiom]
STRUCTURAL_WEIGHT: [High/Medium/Low - how essential to proving the Axiom]"""

    @staticmethod
    def generate_integration_prompt(components: List[Dict], axiom: str) -> str:
        """Generate prompt to integrate components into coherent narrative"""
        component_list = "\n".join([
            f"- {c['name']}: {c['description']} (X: {c.get('deficit_state', '?')} → Y: {c.get('resolution_state', '?')})"
            for c in components
        ])

        return f"""Integrate these validated components into a coherent narrative under Axiom: "{axiom}"

VALIDATED COMPONENTS:
{component_list}

Create a narrative outline that:
1. Starts with the initial deficit implied by the Axiom
2. Sequences components so each component's Y creates the context for the next component's X
3. Ends with a resolution that proves or thoroughly tests the Axiom
4. Ensures no component is redundant or isolated

Provide:
NARRATIVE_TITLE: [Story title]
LOG_LINE: [One-sentence summary]
STRUCTURAL_FLOW: [X→Y chain showing how components connect]
FINAL_STATE: [How the narrative resolves in relation to the Axiom]
MISSING_LINKS: [Any gaps that need additional components]"""


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

import argparse

def main():
    parser = argparse.ArgumentParser(description="NEBRASKA 2.x Narrative Runtime System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Create new narrative
    create_parser = subparsers.add_parser("create", help="Create new narrative state")
    create_parser.add_argument("--axiom", required=True, help="Governing axiom")
    create_parser.add_argument("--description", help="Axiom description")
    create_parser.add_argument("--output", default="narrative_state.json", help="Output file")

    # Add component
    add_parser = subparsers.add_parser("add", help="Add narrative component")
    add_parser.add_argument("--file", required=True, help="Narrative state file")
    add_parser.add_argument("--name", required=True, help="Component name")
    add_parser.add_argument("--type", choices=[t.value for t in ComponentType],
                          default="character", help="Component type")
    add_parser.add_argument("--description", required=True, help="Component description")
    add_parser.add_argument("--x", help="Deficit state (X)")
    add_parser.add_argument("--y", help="Resolution state (Y)")
    add_parser.add_argument("--logic", help="Conversion logic")

    # Validate component
    validate_parser = subparsers.add_parser("validate", help="Validate component")
    validate_parser.add_argument("--file", required=True, help="Narrative state file")
    validate_parser.add_argument("--component-id", help="Specific component ID")
    validate_parser.add_argument("--all", action="store_true", help="Validate all components")

    # Analyze narrative
    analyze_parser = subparsers.add_parser("analyze", help="Analyze narrative state")
    analyze_parser.add_argument("--file", required=True, help="Narrative state file")

    # Generate prompt
    prompt_parser = subparsers.add_parser("prompt", help="Generate LLM prompts")
    prompt_parser.add_argument("--type", choices=["axiom", "validate", "generate", "integrate"],
                             required=True, help="Prompt type")
    prompt_parser.add_argument("--input", help="Input text/concept")
    prompt_parser.add_argument("--file", help="Narrative state file (for component prompts)")

    args = parser.parse_args()

    if args.command == "create":
        axiom = Axiom(statement=args.axiom, description=args.description or "")
        state = NarrativeState(axiom)
        state.save_to_file(args.output)
        print(f"Created new narrative with axiom: {axiom.statement}")
        print(f"Saved to: {args.output}")

    elif args.command == "add":
        state = NarrativeState.load_from_file(args.file)

        component = NarrativeComponent()
        component.name = args.name
        component.component_type = ComponentType(args.type)
        component.description = args.description
        component.deficit_state = args.x or ""
        component.resolution_state = args.y or ""
        component.conversion_logic = args.logic or ""

        component_id = state.add_component(component)

        # Run initial validation
        result = state.validate_pipeline(component_id)

        state.save_to_file(args.file)

        print(f"Added component: {component.name} (ID: {component_id})")
        print(f"Validation: {'PASSED' if result['success'] else 'FAILED'}")
        if not result['success'] and result['stages']:
            last_stage = result['stages'][-1]
            print(f"Failed at: {last_stage['axis']}")
            for note in last_stage['notes']:
                print(f"  - {note}")

    elif args.command == "validate":
        state = NarrativeState.load_from_file(args.file)

        if args.all:
            results = state.validate_all_components()
            print(f"Validation complete:")
            print(f"  Total: {results['total']}")
            print(f"  Valid: {results['valid']}")
            print(f"  Rejected: {results['rejected']}")
            print(f"  Coherence Score: {results['narrative_coherence_score']:.2f}")

            # Show rejected components
            rejected = state.get_rejected_components()
            if rejected:
                print("\nRejected components:")
                for comp in rejected:
                    print(f"  - {comp.name}: {comp.validation_failures[-1] if comp.validation_failures else 'Unknown reason'}")

        elif args.component_id:
            result = state.validate_pipeline(args.component_id)
            print(f"Validation result for {result['component_name']}:")

            for stage in result['stages']:
                status = "✓" if stage['success'] else "✗"
                print(f"  {status} {stage['axis']}: {stage['description']}")
                if not stage['success'] and stage['notes']:
                    for note in stage['notes'][:2]:  # Show first 2 notes
                        print(f"    - {note}")

            print(f"\nFinal state: {result['final_state']}")
            print(f"Overall: {'VALID' if result['success'] else 'INVALID'}")

        state.save_to_file(args.file)

    elif args.command == "analyze":
        state = NarrativeState.load_from_file(args.file)

        print(f"Narrative Analysis")
        print(f"Axiom: {state.axiom.statement}")
        print(f"Total components: {len(state.components)}")

        valid = state.get_valid_components()
        print(f"Valid components: {len(valid)}")

        # Show valid component chain
        if valid:
            print("\nValid Component Chain:")
            for i, comp in enumerate(valid, 1):
                print(f"{i}. {comp.name}")
                print(f"   X: {comp.deficit_state}")
                print(f"   Y: {comp.resolution_state}")
                if comp.depends_on:
                    dep_names = [state.get_component(d).name for d in comp.depends_on
                               if state.get_component(d)]
                    print(f"   Depends on: {', '.join(dep_names)}")
                print()

        # Analyze gaps
        gaps = state.analyze_narrative_gaps()
        if gaps:
            print("\nNarrative Gaps Found:")
            for gap in gaps:
                print(f"  {gap['type'].upper()}: {gap['description']}")
        else:
            print("\nNo structural gaps detected.")

    elif args.command == "prompt":
        engine = NebraskaPromptEngine()

        if args.type == "axiom":
            if not args.input:
                print("Error: --input required for axiom prompt generation")
                return

            prompt = engine.generate_axiom_extraction_prompt(args.input)
            print("=" * 60)
            print("AXIOM EXTRACTION PROMPT")
            print("=" * 60)
            print(prompt)

        elif args.type == "validate":
            if not args.file:
                print("Error: --file required for validate prompt")
                return

            state = NarrativeState.load_from_file(args.file)

            # Get first component for example
            if state.components:
                comp = list(state.components.values())[0]
                comp_dict = comp.to_dict()
                prompt = engine.generate_component_validation_prompt(comp_dict, state.axiom.statement)

                print("=" * 60)
                print("COMPONENT VALIDATION PROMPT")
                print("=" * 60)
                print(prompt)
            else:
                print("No components in narrative state")

        elif args.type == "generate":
            if not args.input:
                print("Error: --input required for generate prompt (provide axiom)")
                return

            axiom = args.input
            component_type = "character"  # Default
            prompt = engine.generate_component_generation_prompt(axiom, component_type)

            print("=" * 60)
            print("COMPONENT GENERATION PROMPT")
            print("=" * 60)
            print(prompt)

        elif args.type == "integrate":
            if not args.file:
                print("Error: --file required for integrate prompt")
                return

            state = NarrativeState.load_from_file(args.file)
            valid_comps = [c.to_dict() for c in state.get_valid_components()]

            if valid_comps:
                prompt = engine.generate_integration_prompt(valid_comps, state.axiom.statement)

                print("=" * 60)
                print("NARRATIVE INTEGRATION PROMPT")
                print("=" * 60)
                print(prompt)
            else:
                print("No valid components to integrate")

    else:
        parser.print_help()


# ============================================================================
# EXAMPLE USAGE & TESTING
# ============================================================================

def run_example():
    """Run an example narrative through the system"""
    print("NEBRASKA 2.x Runtime System - Example Narrative")
    print("=" * 60)

    # Create a narrative about haunted houses
    axiom = Axiom(
        statement="Hauntings require an architect",
        description="Supernatural phenomena have human causes or creators"
    )

    state = NarrativeState(axiom)

    # Add components
    demolisher = NarrativeComponent(
        name="The Demolisher",
        component_type=ComponentType.CHARACTER,
        description="Contractor hired to tear down haunted houses",
        deficit_state="Unresolved supernatural danger in the community",
        resolution_state="Physical safety through destruction of haunted structures",
        conversion_logic="Under the axiom 'hauntings require an architect', the demolisher removes the architectural manifestation of hauntings, thus eliminating the danger by destroying its required vessel."
    )

    architect = NarrativeComponent(
        name="The Architect",
        component_type=ComponentType.CHARACTER,
        description="Original builder of the haunted houses",
        deficit_state="Unacknowledged guilt and repressed trauma",
        resolution_state="Confronted truth and architectural accountability",
        conversion_logic="The architect's unresolved personal issues (X) become manifest in flawed designs that enable hauntings. Confronting this truth (Y) tests the axiom by showing human psychology as the true architect of hauntings."
    )

    haunted_house = NarrativeComponent(
        name="The Gable House",
        component_type=ComponentType.SETTING,
        description="A Victorian house with a history of disappearances",
        deficit_state="Structural instability both physical and metaphysical",
        resolution_state="Revealed as a deliberate trap designed by the architect",
        conversion_logic="The house's haunting phenomena (X) are revealed to be engineered features (Y), proving the axiom that hauntings don't just happen but are built."
    )

    # Add decorative component (should fail validation)
    decorative_ghost = NarrativeComponent(
        name="Floating Apparition",
        component_type=ComponentType.CHARACTER,
        description="A spooky ghost that floats through walls",
        deficit_state="",  # No specific deficit
        resolution_state="Atmospheric creepiness",  # Not a valid resolution
        conversion_logic="It's scary because ghosts are scary."
    )

    # Add components to state
    state.add_component(demolisher)
    state.add_component(architect)
    state.add_component(haunted_house)
    state.add_component(decorative_ghost)

    # Set up dependencies
    demolisher.depends_on = [haunted_house.id]
    architect.enables = [haunted_house.id]
    haunted_house.depends_on = [architect.id]
    haunted_house.enables = [demolisher.id]

    # Validate all components
    print("Validating narrative components...")
    results = state.validate_all_components()

    print(f"\nResults:")
    print(f"  Total components: {results['total']}")
    print(f"  Valid: {results['valid']}")
    print(f"  Rejected: {results['rejected']}")
    print(f"  Narrative Coherence Score: {results['narrative_coherence_score']:.2f}")

    # Show valid component chain
    print("\nValid Component Chain:")
    valid_components = state.get_valid_components()
    for comp in valid_components:
        print(f"  ✓ {comp.name}: {comp.get_conversion_summary()}")

    # Show rejected components
    rejected = state.get_rejected_components()
    if rejected:
        print("\nRejected Components:")
        for comp in rejected:
            print(f"  ✗ {comp.name}")
            if comp.validation_failures:
                print(f"     Reason: {comp.validation_failures[0]}")

    # Analyze gaps
    print("\nAnalyzing narrative gaps...")
    gaps = state.analyze_narrative_gaps()
    if gaps:
        for gap in gaps:
            print(f"  ⚠ {gap['type']}: {gap['description']}")
    else:
        print("  ✓ No structural gaps detected")

    # Save the state
    state.save_to_file("example_narrative.json")
    print(f"\nNarrative state saved to: example_narrative.json")

    # Generate a prompt for LLM integration
    print("\n" + "=" * 60)
    print("LLM Integration Example:")
    print("=" * 60)

    engine = NebraskaPromptEngine()
    prompt = engine.generate_integration_prompt(
        [c.to_dict() for c in valid_components],
        axiom.statement
    )

    print(prompt[:500] + "..." if len(prompt) > 500 else prompt)

    return state


if __name__ == "__main__":
    # If run directly, show example
    import sys

    if len(sys.argv) > 1:
        main()
    else:
        print("No command line arguments provided. Running example...")
        run_example()
        print("\nFor command line usage: python nebraska_runtime.py --help")
