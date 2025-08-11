#!/usr/bin/env python3
"""
Test script for Privacy Instructions Parser

Tests the loading, validation, and parsing of privacy instruction YAML files.
"""

import asyncio
import logging
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from privacy_instructions import PrivacyInstructionParser, ProtectionLevel, ContentSensitivity

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_privacy_instruction_loading():
    """Test loading and parsing of privacy instruction files."""
    
    # Path to privacy instructions
    instructions_path = Path("/Users/matthewprewitt/datasite/datasites/mtprewitt@gmail.com/private/.privacy_instructions")
    
    logger.info(f"Testing privacy instruction loading from: {instructions_path}")
    
    if not instructions_path.exists():
        logger.error(f"Privacy instructions directory not found: {instructions_path}")
        return False
    
    # Initialize parser
    parser = PrivacyInstructionParser(instructions_path)
    
    # Load all instructions
    logger.info("Loading all privacy instruction files...")
    loaded_instructions = await parser.load_all_instructions()
    
    logger.info(f"Loaded {len(loaded_instructions)} document-specific instruction files")
    
    # Test global defaults
    if parser.global_defaults:
        logger.info("✅ Global defaults loaded successfully")
        logger.info(f"   - Schema version: {parser.global_defaults.schema_version}")
        logger.info(f"   - Default protection: {parser.global_defaults.fallback_config.default_protection_level}")
        logger.info(f"   - Entropy budget: {parser.global_defaults.privacy_budget.total_entropy_budget}")
    else:
        logger.warning("❌ Global defaults not found")
    
    # Test document-specific instructions
    test_documents = ["the_algorithm.txt", "research_notes.txt"]
    
    for doc_name in test_documents:
        logger.info(f"\n--- Testing instructions for: {doc_name} ---")
        
        instructions = parser.get_instructions_for_document(doc_name)
        if instructions:
            logger.info("✅ Instructions loaded successfully")
            logger.info(f"   - Document type: {instructions.document_config.document_type}")
            logger.info(f"   - Sensitivity: {instructions.document_config.content_sensitivity}")
            logger.info(f"   - Protected facts: {len(instructions.protected_facts)}")
            logger.info(f"   - Protected themes: {len(instructions.protected_themes)}")
            logger.info(f"   - Entropy budget: {instructions.privacy_budget.total_entropy_budget}")
            logger.info(f"   - Max queries/day: {instructions.privacy_budget.max_queries_per_day}")
            
            # Test protected facts parsing
            for i, fact in enumerate(instructions.protected_facts[:2]):  # Show first 2
                logger.info(f"   - Protected fact {i+1}: {fact.category} ({fact.protection_level})")
                logger.info(f"     Items: {fact.items[:2]}...")  # Show first 2 items
            
            # Test protected themes parsing
            for i, theme in enumerate(instructions.protected_themes[:2]):  # Show first 2
                logger.info(f"   - Protected theme {i+1}: {theme.theme} (abstraction: {theme.abstraction_level})")
            
            # Test response behaviors
            direct_strategy = instructions.response_behavior.direct_fact_queries.get("strategy", "unknown")
            logger.info(f"   - Direct fact query strategy: {direct_strategy}")
            
            # Test integrity validation
            is_valid = parser.validate_instruction_integrity(instructions)
            logger.info(f"   - Integrity check: {'✅ Valid' if is_valid else '❌ Invalid'}")
            
        else:
            logger.error(f"❌ No instructions found for: {doc_name}")
    
    # Test non-existent document (should fall back to defaults)
    logger.info(f"\n--- Testing fallback for unknown document ---")
    unknown_instructions = parser.get_instructions_for_document("unknown_file.txt")
    if unknown_instructions:
        logger.info("✅ Fallback to global defaults works")
        logger.info(f"   - Using document: {unknown_instructions.document_config.target_document}")
        logger.info(f"   - Protection level: {unknown_instructions.fallback_config.default_protection_level}")
    else:
        logger.error("❌ No fallback instructions available")
    
    logger.info(f"\n--- Test Summary ---")
    logger.info(f"Total instruction files loaded: {len(loaded_instructions)}")
    logger.info(f"Global defaults available: {'✅' if parser.global_defaults else '❌'}")
    
    return len(loaded_instructions) > 0 or parser.global_defaults is not None

async def test_privacy_instruction_validation():
    """Test validation of privacy instruction structure."""
    
    logger.info("\n=== Testing Privacy Instruction Validation ===")
    
    instructions_path = Path("/Users/matthewprewitt/datasite/datasites/mtprewitt@gmail.com/private/.privacy_instructions")
    parser = PrivacyInstructionParser(instructions_path)
    
    # Test loading specific files
    test_files = [
        "the_algorithm.yaml",
        "research_notes.yaml", 
        "global_defaults.yaml"
    ]
    
    for filename in test_files:
        file_path = instructions_path / filename
        if file_path.exists():
            logger.info(f"\n--- Validating: {filename} ---")
            
            instructions = await parser.load_instructions(file_path)
            if instructions and instructions.is_valid:
                logger.info("✅ File validation passed")
                logger.info(f"   - Schema version: {instructions.schema_version}")
                logger.info(f"   - Validation errors: {len(instructions.validation_errors)}")
                
                if instructions.validation_errors:
                    for error in instructions.validation_errors:
                        logger.warning(f"   - Warning: {error}")
                        
            else:
                logger.error(f"❌ File validation failed: {filename}")
                if instructions and instructions.validation_errors:
                    for error in instructions.validation_errors:
                        logger.error(f"   - Error: {error}")
        else:
            logger.warning(f"⚠️ File not found: {filename}")
    
    return True

async def main():
    """Run all privacy instruction tests."""
    
    logger.info("=== Privacy Instruction Parser Tests ===\n")
    
    # Test loading
    loading_success = await test_privacy_instruction_loading()
    
    # Test validation
    validation_success = await test_privacy_instruction_validation()
    
    # Summary
    logger.info(f"\n=== Test Results ===")
    logger.info(f"Loading tests: {'✅ PASSED' if loading_success else '❌ FAILED'}")
    logger.info(f"Validation tests: {'✅ PASSED' if validation_success else '❌ FAILED'}")
    
    overall_success = loading_success and validation_success
    logger.info(f"Overall: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    return overall_success

if __name__ == "__main__":
    asyncio.run(main())