"""
Client-Side Rendering Logic for Processed Data Pods

[INFO] CRITICAL: This renders data pods that have been locally processed
- Images already decrypted and converted to base64
- Audio already extracted and ready to play
- Type-based rendering for different image types
"""

from typing import Dict, Any, List


def render_processed_data_pod(data_pod: Dict[str, Any]) -> str:
    """
    Render processed data pod (already decrypted) as HTML
    
    Args:
        data_pod: Processed data pod with decrypted content
        
    Returns:
        str: HTML string for rendering
    """
    html_parts = []
    
    # Add processing info header
    if data_pod.get('processed_at'):
        html_parts.append(f"""
        <div class="processing-status">
            <h3>[UNLOCK] Decrypted Content</h3>
            <p>Processed: {format_timestamp(data_pod['processed_at'])}</p>
            <p>Items: {len(data_pod.get('items', []))}</p>
            <p>With Audio: {len([i for i in data_pod.get('items', []) if i.get('hasAudio')])}</p>
            {render_type_stats(data_pod.get('type_distribution', {}))}
        </div>
        """)
    
    # Render items
    for item in data_pod.get('items', []):
        html_parts.append(render_data_pod_item(item))
    
    return ''.join(html_parts)


def render_data_pod_item(item: Dict[str, Any]) -> str:
    """
    Render individual item (already decrypted)
    
    Args:
        item: Data pod item with decrypted content
        
    Returns:
        str: HTML string for item
    """
    image_type = item.get('imageType', 'original')
    has_audio = item.get('hasAudio', False)
    audio_method = item.get('audioMethod', 'metadata')
    
    html_parts = []
    
    # Item container
    html_parts.append(f'''
    <div class="data-pod-item {image_type}">
    ''')
    
    # Image (already converted to base64 during processing)
    if item.get('renditions') and item['renditions']:
        href = item['renditions'][0].get('href', '')
        title = item.get('title', 'Unknown')
        html_parts.append(f'''
        <img src="{href}" alt="{title}" />
        ''')
    
    # Metadata section
    html_parts.append('''
    <div class="metadata">
    ''')
    
    # Title
    title = item.get('title', 'Unknown')
    html_parts.append(f'''
    <h3>{title}</h3>
    ''')
    
    # Type info
    html_parts.append(f'''
    <p>Type: {image_type}</p>
    ''')
    
    # Type-specific badge
    type_label = get_type_label(image_type)
    html_parts.append(f'''
    <p class="type-badge {image_type}">{type_label}</p>
    ''')
    
    # Audio section (already extracted during processing)
    if has_audio and item.get('audio'):
        html_parts.append(render_audio_section(item['audio'], audio_method))
    
    # Additional metadata
    if item.get('byline'):
        html_parts.append(f'<p>By: {item["byline"]}</p>')
    
    if item.get('creditline'):
        html_parts.append(f'<p>Credit: {item["creditline"]}</p>')
    
    if item.get('copyright'):
        html_parts.append(f'<p>© {item["copyright"]}</p>')
    
    html_parts.append('''
    </div>
    </div>
    ''')
    
    return ''.join(html_parts)


def render_audio_section(audio_data: Dict[str, Any], audio_method: str) -> str:
    """
    Render audio section for extracted audio
    
    Args:
        audio_data: Extracted audio data
        audio_method: Audio extraction method
        
    Returns:
        str: HTML string for audio section
    """
    html_parts = []
    
    html_parts.append('''
    <div class="audio-section">
    ''')
    
    # Audio badge
    html_parts.append(f'''
    <p class="audio-badge">[AUDIO] Audio ({audio_method})</p>
    ''')
    
    # Audio player
    audio_format = audio_data.get('format', 'wav')
    audio_base64 = audio_data.get('data', '')
    
    if audio_base64:
        html_parts.append(f'''
        <audio controls>
            <source src="data:audio/{audio_format};base64,{audio_base64}" type="audio/{audio_format}">
            Your browser does not support the audio element.
        </audio>
        ''')
    
    # Audio info
    if audio_data.get('extractedAt'):
        extracted_time = format_timestamp(audio_data['extractedAt'])
        html_parts.append(f'''
        <p class="audio-info">Extracted: {extracted_time}</p>
        ''')
    
    html_parts.append('''
    </div>
    ''')
    
    return ''.join(html_parts)


def get_type_label(image_type: str) -> str:
    """
    Get human-readable type label
    
    Args:
        image_type: Image type
        
    Returns:
        str: Human-readable label
    """
    labels = {
        'raw': 'Original Image',
        'processed': 'Watermarked',
        'aposematic': 'Aposematic',
        'enciphered': 'Enciphered'
    }
    return labels.get(image_type, 'Unknown')


def format_timestamp(timestamp: float) -> str:
    """
    Format timestamp for display
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        str: Formatted timestamp
    """
    import datetime
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def render_type_stats(type_distribution: Dict[str, int]) -> str:
    """
    Render type statistics
    
    Args:
        type_distribution: Type distribution data
        
    Returns:
        str: HTML string for type stats
    """
    if not type_distribution:
        return ''
    
    html_parts = ['''
    <div class="type-stats">
        <h4>Type Distribution:</h4>
    ''']
    
    for type_name, count in type_distribution.items():
        if count > 0:
            html_parts.append(f'<span class="type-stat">{type_name}: {count}</span>')
    
    html_parts.append('''
    </div>
    ''')
    
    return ''.join(html_parts)


def filter_by_type(items: List[Dict[str, Any]], target_type: str) -> List[Dict[str, Any]]:
    """
    Filter items by image type
    
    Args:
        items: List of data pod items
        target_type: Target image type
        
    Returns:
        List[Dict[str, Any]]: Filtered items
    """
    return [item for item in items if item.get('imageType') == target_type]


def calculate_type_stats(items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calculate type statistics
    
    Args:
        items: List of data pod items
        
    Returns:
        Dict[str, int]: Type statistics
    """
    stats = {
        'raw': 0,
        'processed': 0,
        'aposematic': 0,
        'enciphered': 0,
        'withAudio': 0
    }
    
    for item in items:
        image_type = item.get('imageType', 'raw')
        if image_type in stats:
            stats[image_type] += 1
        
        if item.get('hasAudio'):
            stats['withAudio'] += 1
    
    return stats


def create_gallery_html(data_pod: Dict[str, Any], title: str = "Audio Gallery") -> str:
    """
    Create complete HTML gallery page
    
    Args:
        data_pod: Processed data pod
        title: Gallery title
        
    Returns:
        str: Complete HTML page
    """
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        
        .processing-status {{
            background: #e8f5e8;
            border: 1px solid #4caf50;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        
        .data-pod-item {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow: hidden;
        }}
        
        .data-pod-item img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .metadata {{
            padding: 15px;
        }}
        
        .type-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            margin: 5px 0;
        }}
        
        .type-badge.raw {{
            background: #e3f2fd;
            color: #1976d2;
        }}
        
        .type-badge.processed {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}
        
        .type-badge.aposematic {{
            background: #fff3e0;
            color: #f57c00;
        }}
        
        .type-badge.enciphered {{
            background: #ffebee;
            color: #d32f2f;
        }}
        
        .audio-section {{
            margin-top: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        
        .audio-badge {{
            color: #2e7d32;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .audio-info {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        
        .type-stats {{
            margin-top: 10px;
        }}
        
        .type-stat {{
            display: inline-block;
            margin-right: 15px;
            font-size: 14px;
        }}
        
        h1, h2, h3, h4 {{
            color: #333;
        }}
        
        h1 {{
            text-align: center;
            margin-bottom: 30px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {render_processed_data_pod(data_pod)}
</body>
</html>
    '''


def save_gallery_html(data_pod: Dict[str, Any], output_path: str, title: str = "Audio Gallery") -> None:
    """
    Save gallery HTML to file
    
    Args:
        data_pod: Processed data pod
        output_path: Output file path
        title: Gallery title
    """
    html_content = create_gallery_html(data_pod, title)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"[OK] Gallery saved to: {output_path}")


# JavaScript functions for browser integration
def get_javascript_functions() -> str:
    """
    Get JavaScript functions for browser integration
    
    Returns:
        str: JavaScript code
    """
    return '''
// Client-side rendering of processed data pod (already decrypted)
function renderProcessedDataPod(dataPod) {
    const container = document.getElementById('gallery-container');
    container.innerHTML = '';
    
    dataPod.items.forEach(item => {
        const itemElement = renderDataPodItem(item);
        container.appendChild(itemElement);
    });
    
    // Show processing info
    showProcessingInfo(dataPod);
}

// Render individual item (already decrypted)
function renderDataPodItem(item) {
    const { imageType, hasAudio, audioMethod } = item;
    
    // Create item container
    const itemDiv = document.createElement('div');
    itemDiv.className = `data-pod-item ${imageType}`;
    
    // Image (already converted to base64 during processing)
    const img = document.createElement('img');
    img.src = item.renditions[0].href;
    img.alt = item.title;
    itemDiv.appendChild(img);
    
    // Metadata section
    const metadataDiv = document.createElement('div');
    metadataDiv.className = 'metadata';
    
    const title = document.createElement('h3');
    title.textContent = item.title;
    metadataDiv.appendChild(title);
    
    const typeInfo = document.createElement('p');
    typeInfo.textContent = `Type: ${imageType}`;
    metadataDiv.appendChild(typeInfo);
    
    // Type-specific badge
    const typeBadge = document.createElement('p');
    typeBadge.className = `type-badge ${imageType}`;
    typeBadge.textContent = getTypeLabel(imageType);
    metadataDiv.appendChild(typeBadge);
    
    // Audio section (already extracted during processing)
    if (hasAudio && item.audio) {
        const audioSection = document.createElement('div');
        audioSection.className = 'audio-section';
        
        const audioBadge = document.createElement('p');
        audioBadge.className = 'audio-badge';
        audioBadge.textContent = `[AUDIO] Audio (${audioMethod})`;
        audioSection.appendChild(audioBadge);
        
        const audio = document.createElement('audio');
        audio.controls = true;
        
        const source = document.createElement('source');
        source.src = `data:audio/${item.audio.format};base64,${item.audio.data}`;
        source.type = `audio/${item.audio.format}`;
        audio.appendChild(source);
        
        audioSection.appendChild(audio);
        
        const audioInfo = document.createElement('p');
        audioInfo.className = 'audio-info';
        audioInfo.textContent = `Extracted: ${new Date(item.audio.extractedAt * 1000).toLocaleString()}`;
        audioSection.appendChild(audioInfo);
        
        metadataDiv.appendChild(audioSection);
    }
    
    itemDiv.appendChild(metadataDiv);
    return itemDiv;
}

// Get human-readable type label
function getTypeLabel(imageType) {
    const labels = {
        'raw': 'Original Image',
        'processed': 'Watermarked',
        'aposematic': 'Aposematic',
        'enciphered': 'Enciphered'
    };
    return labels[imageType] || 'Unknown';
}

// Show processing information
function showProcessingInfo(dataPod) {
    const infoDiv = document.getElementById('processing-info');
    if (infoDiv && dataPod.processed_at) {
        infoDiv.innerHTML = `
            <div class="processing-status">
                <h3>[UNLOCK] Decrypted Content</h3>
                <p>Processed: ${new Date(dataPod.processed_at * 1000).toLocaleString()}</p>
                <p>Items: ${dataPod.items.length}</p>
                <p>With Audio: ${dataPod.items.filter(i => i.hasAudio).length}</p>
                ${dataPod.type_distribution ? `
                    <div class="type-stats">
                        <h4>Type Distribution:</h4>
                        ${Object.entries(dataPod.type_distribution).map(([type, count]) => 
                            `<span class="type-stat">${type}: ${count}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
}

// Filter and render by type
function filterByType(items, targetType) {
    return items.filter(item => item.imageType === targetType);
}

// Type statistics
function calculateTypeStats(items) {
    const stats = {
        raw: 0,
        processed: 0,
        aposematic: 0,
        enciphered: 0,
        withAudio: 0
    };
    
    items.forEach(item => {
        stats[item.imageType]++;
        if (item.hasAudio) stats.withAudio++;
    });
    
    return stats;
}

// Initialize gallery with processed data pod
async function initializeGallery(dataPodPath, stellarSecret) {
    try {
        // This would call the Python processing function
        // In a real implementation, this might be via API or local processing
        const processedDataPod = await processDataPodLocally(dataPodPath, stellarSecret);
        
        // Render the processed data pod
        renderProcessedDataPod(processedDataPod);
        
    } catch (error) {
        console.error('Failed to initialize gallery:', error);
        showError('Failed to process data pod. Check your Stellar key.');
    }
}
'''
