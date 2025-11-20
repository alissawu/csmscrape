Code to download CSM 1-11 Colored as PDF / EPub.
*No one's telling you to use the code, consider this a grey area side project or something.

1. Make your environment for the dependencies so you don't mess up your root stuff
<br>
I personally use python3 and pip3. You may use pip or something. Just check or download the recent stuff. I recommend just downloading pip3.

```python3 -m venv csm-env```
```source csm-env/bin/activate```
```pip3 install -r requirements.txt```
<br>

2. Run the code
<br>

```python3 csm_all.py```
This will download all the images, then merge them into a PDF per volume
If you want epubs, run 
```python3 csm_epub.py```
This includes a navigation dropdown capability.
Btw you have to run this AFTER running csm_all
<br>

3. Notes
<br>
The initial download was really slow so I sped it up with concurrency but the server has scrape limits so I just kept the max workers at 3 cuz otherwise it gets screwy

