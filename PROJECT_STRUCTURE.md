# MetaHuman Streamer Project Structure

## 📁 Directory Organization

### 🎯 **v1/** - Original Streamer Implementation
- `mh_streamer_gui.py` - Original Tkinter-based streamer
- `channels_steering_from_columns.json` - Original channel configuration
- `sequence_gru.pth` - Original sequence generation model
- `steering_gru.pth` - Original steering classification model
- `baseline_vec.npy` - Original baseline vector
- `gen_left.npy`, `gen_right.npy` - Generated turn sequences
- `X_seq.npy`, `y_seq.npy` - Training sequences and labels
- `norm.json` - Original normalization parameters
- `columns.txt` - Original feature names

### 🚀 **v2/** - Enhanced Streamer Implementation
- `mh_streamer_v2.py` - Enhanced streamer with OSC format
- `preprocessing_v2.py` - V2 data preprocessing and model training
- `osc_channels_config.json` - OSC channel configuration for Unreal
- `channels_steering_from_columns_corrected.json` - Corrected channel config
- `baseline_data.npy` - V2 baseline sequences (20 samples)
- `left_turn_data.npy` - V2 left turn sequences (10 samples)
- `right_turn_data.npy` - V2 right turn sequences (10 samples)
- `baseline_gru.pth` - V2 baseline model
- `left_turn_gru.pth` - V2 left turn model
- `right_turn_gru.pth` - V2 right turn model
- `normalization_params.json` - V2 normalization parameters
- `baseline_vector.npy` - V2 baseline vector
- `training_losses.png` - Training loss visualization

### 📚 **docs/** - Documentation
- `README.md` - Main project documentation
- `PRESENTATION_SUMMARY.md` - Presentation summary
- `osc_manifest.md` - OSC streaming specification
- `osc_mapping.json` - Complete OSC bone mapping
- `*.pdf` - Project presentations and guides

### 🧪 **tests/** - Test Scripts
- `test_streamer_v2.py` - V2 streamer functionality tests
- `test_osc_format.py` - OSC format validation
- `test_channel_mapping.py` - Channel mapping tests
- `test_port_config.py` - Port configuration tests
- `test_osc_reception.py` - OSC reception tests
- `demo_osc_output.py` - OSC output demonstration
- `example_osc_messages.py` - OSC message examples
- `show_data_structure.py` - Data structure visualization
- `test_connection.py` - Connection tests

### 📊 **data/** - Data Storage
- **raw/** - Original CSV data and notebooks
  - `FirstDataset_Clip_data.csv` - Main dataset
  - `BaseLine(SittingPosition).csv` - Baseline data
  - `LeftTurn_10times.csv` - Left turn data
  - `RightTurn_10times.csv` - Right turn data
  - `steering_signals.csv` - Steering signals
  - `hand_movement_stats.csv` - Hand movement statistics
  - `PreProcessing.ipynb` - Original preprocessing notebook
  - `Untitled.ipynb` - Additional notebooks
  - `Try.py` - Experimental scripts
- **bonelist/** - Bone mapping files
  - `MetaHuman_FullSkeleton.csv` - Complete skeleton mapping

### 🔧 **Root Files** - Project Configuration
- `requirements.txt` - Python dependencies
- `install_and_run.sh` - Installation script
- `.gitignore` - Git ignore rules

## 🎯 **Key Differences: V1 vs V2**

### **V1 Streamer:**
- Uses `/mh/feature_name` OSC addresses
- Single GRU model for all movements
- Basic channel configuration
- Limited to 16 channels

### **V2 Streamer:**
- Uses `/bone/{bone}/{axis}` OSC addresses (Unreal compatible)
- Separate GRU models per movement type
- Advanced OSC configuration with transforms
- 37 channels with bone distribution
- Enhanced logging and debugging
- Configurable OSC ports

## 🚀 **Usage**

### **Run V1 Streamer:**
```bash
cd v1
python mh_streamer_gui.py
```

### **Run V2 Streamer:**
```bash
cd v2
python mh_streamer_v2.py
```

### **Run Tests:**
```bash
cd tests
python test_streamer_v2.py
python test_osc_format.py
```
