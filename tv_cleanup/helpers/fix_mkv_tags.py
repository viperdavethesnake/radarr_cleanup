#!/usr/bin/env python3

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

def create_episode_tags_xml(episode_data):
    """Create XML tags for an episode"""
    root = ET.Element("Tags")
    
    # Global tag
    tag = ET.SubElement(root, "Tag")
    targets = ET.SubElement(tag, "Targets")
    target = ET.SubElement(targets, "Target")
    target_type = ET.SubElement(target, "TargetTypeValue")
    target_type.text = "50"  # Movie/episode
    
    # Add episode information
    simple_tags = ET.SubElement(tag, "Simple")
    
    # Title
    title_tag = ET.SubElement(simple_tags, "Tag")
    name = ET.SubElement(title_tag, "Name")
    name.text = "TITLE"
    string = ET.SubElement(title_tag, "String")
    string.text = episode_data.get('title', '')
    
    # Episode number
    episode_tag = ET.SubElement(simple_tags, "Tag")
    name = ET.SubElement(episode_tag, "Name")
    name.text = "EPISODE_NUMBER"
    string = ET.SubElement(episode_tag, "String")
    string.text = str(episode_data.get('episode', ''))
    
    # Season number
    season_tag = ET.SubElement(simple_tags, "Tag")
    name = ET.SubElement(season_tag, "Name")
    name.text = "SEASON_NUMBER"
    string = ET.SubElement(season_tag, "String")
    string.text = str(episode_data.get('season', ''))
    
    # Show name
    show_tag = ET.SubElement(simple_tags, "Tag")
    name = ET.SubElement(show_tag, "Name")
    name.text = "SHOW_NAME"
    string = ET.SubElement(show_tag, "String")
    string.text = episode_data.get('show_name', '')
    
    # TMDB ID
    tmdb_tag = ET.SubElement(simple_tags, "Tag")
    name = ET.SubElement(tmdb_tag, "Name")
    name.text = "TMDB_ID"
    string = ET.SubElement(tmdb_tag, "String")
    string.text = str(episode_data.get('tmdb_id', ''))
    
    # Description/Plot
    if episode_data.get('description'):
        desc_tag = ET.SubElement(simple_tags, "Tag")
        name = ET.SubElement(desc_tag, "Name")
        name.text = "DESCRIPTION"
        string = ET.SubElement(desc_tag, "String")
        string.text = episode_data.get('description', '')
    
    return ET.tostring(root, encoding='unicode')

def add_episode_metadata(mkv_file, episode_data):
    """Add episode metadata to MKV file using tags"""
    try:
        # Create temporary XML file with tags
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_file:
            xml_content = create_episode_tags_xml(episode_data)
            temp_file.write(xml_content)
            temp_file_path = temp_file.name
        
        # Add tags to MKV file
        cmd = ['mkvpropedit', '--tags', f'global:{temp_file_path}', mkv_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if result.returncode == 0:
            print(f"✅ Added metadata to: {os.path.basename(mkv_file)}")
            return True
        else:
            print(f"❌ Error adding metadata to {mkv_file}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Exception adding metadata to {mkv_file}: {e}")
        return False

def test_episode_metadata():
    """Test adding metadata to one episode"""
    episode_data = {
        'title': 'Pilot',
        'episode': 1,
        'season': 1,
        'show_name': 'Glee',
        'tmdb_id': 1417,
        'description': 'Optimistic high school teacher Will Schuester tries to refuel his own passion while reinventing the McKinley High School\'s glee club and challenging a group of outcasts to realize their star potential.'
    }
    
    mkv_file = "/storage/media/servarr/tvshows_tagged/Glee_(2009)/Season_01/Glee_-_S01E01_-_Pilot.mkv"
    
    if os.path.exists(mkv_file):
        print("Testing MKV tag addition...")
        success = add_episode_metadata(mkv_file, episode_data)
        if success:
            print("✅ Test successful!")
        else:
            print("❌ Test failed!")
    else:
        print(f"❌ File not found: {mkv_file}")

if __name__ == "__main__":
    test_episode_metadata() 