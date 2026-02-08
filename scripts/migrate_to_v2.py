#!/usr/bin/env python3
"""
Migration script from v1 to v2 (refactored version)
SIGNAL-ALERT System Migration Tool
"""

import os
import json
import shutil
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def backup_current_data():
    """Backup current data before migration"""
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
        
        # Backup data directory
        if os.path.exists('data'):
            shutil.copytree('data', f'{backup_dir}/data')
            logger.info(f"✅ Data directory backed up")
        
        # Backup config files
        config_files = ['config/settings.py', 'requirements.txt', 'cloudbuild.yaml']
        for config_file in config_files:
            if os.path.exists(config_file):
                dest_file = f"{backup_dir}/{config_file.replace('/', '_')}"
                shutil.copy2(config_file, dest_file)
                logger.info(f"✅ {config_file} backed up")
        
        # Backup key service files
        service_files = [
            'app/services/data_updater.py',
            'app/services/price_fetcher.py',
            'app/services/position_tracker.py'
        ]
        
        service_backup_dir = f"{backup_dir}/old_services"
        os.makedirs(service_backup_dir, exist_ok=True)
        
        for service_file in service_files:
            if os.path.exists(service_file):
                dest_file = f"{service_backup_dir}/{os.path.basename(service_file)}"
                shutil.copy2(service_file, dest_file)
                logger.info(f"✅ {service_file} backed up")
        
        logger.info(f"🎉 All data backed up to {backup_dir}")
        return backup_dir
        
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        raise

def migrate_positions_format():
    """Migrate positions.json to new format if needed"""
    positions_file = 'data/positions.json'
    
    if not os.path.exists(positions_file):
        logger.info("ℹ️ No positions.json found, skipping position migration")
        return
    
    try:
        logger.info("🔄 Checking positions.json format...")
        
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        
        # Check if migration needed (detect old format)
        needs_migration = False
        migrated_count = 0
        
        for pos_id, pos_data in positions.items():
            # Convert datetime objects to ISO strings
            if 'entry_time' in pos_data:
                if not isinstance(pos_data['entry_time'], str):
                    try:
                        if hasattr(pos_data['entry_time'], 'isoformat'):
                            pos_data['entry_time'] = pos_data['entry_time'].isoformat()
                        else:
                            pos_data['entry_time'] = str(pos_data['entry_time'])
                        needs_migration = True
                        migrated_count += 1
                    except Exception as e:
                        logger.warning(f"Could not migrate entry_time for {pos_id}: {e}")
            
            # Ensure required fields exist
            if 'last_update' not in pos_data:
                pos_data['last_update'] = datetime.now().isoformat()
                needs_migration = True
            
            if 'created_by' not in pos_data:
                pos_data['created_by'] = 'legacy_system'
                needs_migration = True
            
            # Ensure signal_strength exists
            if 'signal_strength' not in pos_data:
                pos_data['signal_strength'] = 75.0  # Default value
                needs_migration = True
        
        if needs_migration:
            # Create backup of original
            backup_file = f"{positions_file}.pre_v2_backup"
            shutil.copy2(positions_file, backup_file)
            logger.info(f"📋 Original positions backed up to {backup_file}")
            
            # Save migrated data
            with open(positions_file, 'w', encoding='utf-8') as f:
                json.dump(positions, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Positions format migrated ({migrated_count} positions updated)")
        else:
            logger.info("ℹ️ Positions format already up to date")
            
    except Exception as e:
        logger.error(f"❌ Position migration failed: {e}")
        raise

def migrate_candle_data():
    """Check and migrate candle data format if needed"""
    candles_dir = 'data/candles'
    
    if not os.path.exists(candles_dir):
        logger.info("ℹ️ No candles directory found, skipping candle migration")
        return
    
    try:
        logger.info("🔄 Checking candle data format...")
        
        migrated_files = 0
        for filename in os.listdir(candles_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(candles_dir, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Check if data needs structure update
                    needs_update = False
                    
                    if isinstance(data, list):
                        # Old format: direct list of candles
                        # Convert to new format with metadata
                        symbol_interval = filename.replace('.json', '').split('_')
                        if len(symbol_interval) >= 2:
                            symbol = symbol_interval[0]
                            interval = symbol_interval[1]
                            
                            new_data = {
                                'symbol': symbol,
                                'interval': interval,
                                'timestamp': datetime.now().isoformat(),
                                'data': data,
                                'migrated_from': 'v1'
                            }
                            
                            # Backup original
                            backup_file = f"{file_path}.v1_backup"
                            shutil.copy2(file_path, backup_file)
                            
                            # Save new format
                            with open(file_path, 'w', encoding='utf-8') as f:
                                json.dump(new_data, f, ensure_ascii=False, indent=2)
                            
                            migrated_files += 1
                            needs_update = True
                
                except Exception as e:
                    logger.warning(f"Could not check/migrate {filename}: {e}")
        
        if migrated_files > 0:
            logger.info(f"✅ Migrated {migrated_files} candle data files")
        else:
            logger.info("ℹ️ Candle data format already up to date")
            
    except Exception as e:
        logger.error(f"❌ Candle data migration failed: {e}")
        logger.info("ℹ️ Continuing with migration (candle data migration is optional)")

def create_new_directories():
    """Create required directories for v2"""
    directories = [
        'scripts',
        'tests',
        'data/logs'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"✅ Created directory: {directory}")
        except Exception as e:
            logger.warning(f"Could not create directory {directory}: {e}")

def cleanup_deprecated_files():
    """Move deprecated files to backup location"""
    deprecated_files = [
        'app/services/price_fetcher.py',      # Replaced by DataManager
        'app/services/data_updater.py',       # Replaced by DataManager  
        'app/services/position_tracker.py',   # Replaced by PositionManager
    ]
    
    deprecated_dir = 'deprecated_v1_files'
    os.makedirs(deprecated_dir, exist_ok=True)
    
    moved_files = 0
    for file_path in deprecated_files:
        if os.path.exists(file_path):
            try:
                dest_file = os.path.join(deprecated_dir, os.path.basename(file_path))
                shutil.move(file_path, dest_file)
                logger.info(f"🗑️ Moved {file_path} to {dest_file}")
                moved_files += 1
            except Exception as e:
                logger.warning(f"Could not move {file_path}: {e}")
    
    if moved_files > 0:
        logger.info(f"✅ Moved {moved_files} deprecated files")
    else:
        logger.info("ℹ️ No deprecated files found to move")

def verify_migration():
    """Verify migration completed successfully"""
    required_files = [
        'app/utils/core_utils.py',
        'app/utils/data_types.py',
        'app/services/data_manager.py',
        'app/services/position_manager.py',
        'app/services/config_manager.py',
        'tests/test_integration.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"❌ Migration incomplete. Missing files:")
        for file_path in missing_files:
            logger.error(f"   - {file_path}")
        return False
    
    # Check if new files have content
    empty_files = []
    for file_path in required_files:
        try:
            if os.path.getsize(file_path) == 0:
                empty_files.append(file_path)
        except Exception:
            empty_files.append(file_path)
    
    if empty_files:
        logger.warning(f"⚠️ Empty files detected (need to add code):")
        for file_path in empty_files:
            logger.warning(f"   - {file_path}")
        logger.info("ℹ️ This is normal if you haven't added the refactored code yet")
    
    logger.info("✅ Migration verification passed")
    return True

def generate_migration_report(backup_dir):
    """Generate migration report"""
    report_file = f"{backup_dir}/migration_report.txt"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("SIGNAL-ALERT v1 to v2 Migration Report\n")
            f.write("=" * 50 + "\n")
            f.write(f"Migration Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Backup Location: {backup_dir}\n\n")
            
            f.write("Files Migrated:\n")
            f.write("- data/positions.json (format updated)\n")
            f.write("- data/candles/*.json (structure updated if needed)\n\n")
            
            f.write("New Files Created:\n")
            new_files = [
                'app/utils/core_utils.py',
                'app/utils/data_types.py', 
                'app/services/data_manager.py',
                'app/services/position_manager.py',
                'app/services/config_manager.py',
                'tests/test_integration.py'
            ]
            
            for file_path in new_files:
                status = "✅ Created" if os.path.exists(file_path) else "❌ Missing"
                f.write(f"- {file_path} {status}\n")
            
            f.write("\nDeprecated Files Moved:\n")
            deprecated_files = [
                'price_fetcher.py',
                'data_updater.py', 
                'position_tracker.py'
            ]
            
            for filename in deprecated_files:
                f.write(f"- {filename} -> deprecated_v1_files/\n")
            
            f.write("\nNext Steps:\n")
            f.write("1. Add refactored code to new files\n")
            f.write("2. Update imports in existing files\n")
            f.write("3. Test the system locally\n")
            f.write("4. Deploy to Cloud Run\n")
            f.write("5. Monitor for 24-48 hours\n")
            f.write("6. Remove backup files after confirmation\n")
        
        logger.info(f"📊 Migration report saved to {report_file}")
        
    except Exception as e:
        logger.warning(f"Could not generate migration report: {e}")

def main():
    """Main migration function"""
    print("🚀 Starting SIGNAL-ALERT v1 to v2 Migration")
    print("=" * 60)
    
    try:
        # Step 1: Backup
        logger.info("Step 1: Creating backup...")
        backup_dir = backup_current_data()
        
        # Step 2: Create directories
        logger.info("Step 2: Creating required directories...")
        create_new_directories()
        
        # Step 3: Migrate data formats
        logger.info("Step 3: Migrating data formats...")
        migrate_positions_format()
        migrate_candle_data()
        
        # Step 4: Cleanup
        logger.info("Step 4: Cleaning up deprecated files...")
        cleanup_deprecated_files()
        
        # Step 5: Verify
        logger.info("Step 5: Verifying migration...")
        if verify_migration():
            logger.info("Step 6: Generating migration report...")
            generate_migration_report(backup_dir)
            
            print("\n🎉 Migration completed successfully!")
            print("\n📋 Next steps:")
            print("1. Add refactored code to the new empty files")
            print("2. Update imports in existing service files")
            print("3. Run tests: python -m pytest tests/")
            print("4. Test locally: python app/main.py")
            print("5. Deploy to Cloud Run")
            print("6. Monitor system for 24 hours")
            print(f"7. Remove backup files ({backup_dir}) after confirmation")
            print("\n📊 Check migration report for details:")
            print(f"   cat {backup_dir}/migration_report.txt")
        else:
            print("\n❌ Migration verification failed. Please check missing files.")
            print("ℹ️ You may need to create the new files manually and add the refactored code.")
            
    except KeyboardInterrupt:
        print("\n⚠️ Migration cancelled by user")
        logger.info("Migration cancelled")
    except Exception as e:
        print(f"\n💥 Migration error: {e}")
        logger.error(f"Migration failed: {e}")
        print("Please restore from backup and try again, or perform migration manually.")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())