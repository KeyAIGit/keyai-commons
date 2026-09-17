"""Offline arithmetic only. No device discovery, training, or capacity claims."""
import argparse,json,math

def estimate(installs:int,online:float,eligible:float,useful:float,update_mb:float,upload_mbps:float,dataset_gb:float,recipients:int,host_upload_mbps:float):
    if installs<0 or recipients<0 or any(not 0<=p<=1 for p in (online,eligible,useful)):
        raise ValueError('Counts must be nonnegative and fractions must be 0..1')
    if any(not math.isfinite(x) or x<=0 for x in (update_mb,upload_mbps,dataset_gb,host_upload_mbps)):
        raise ValueError('All sizes and rates must be finite and positive')
    return {'eligible_online_nodes':installs*online*eligible,
            'useful_compute_equivalents':installs*online*eligible*useful,
            'ideal_update_upload_seconds':update_mb*8/upload_mbps,
            'distribution_decimal_TB':dataset_gb*recipients/1000,
            'single_host_ideal_distribution_days':dataset_gb*recipients*8000/host_upload_mbps/86400,
            'scope':'Hypothetical equal-speed nodes. No measured GPU capacity, bandwidth, energy or training-quality guarantee.'}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installs',type=int,default=1000000);p.add_argument('--online',type=float,default=.1)
    p.add_argument('--eligible',type=float,default=.5);p.add_argument('--useful',type=float,default=.2)
    p.add_argument('--update-mb',type=float,default=200);p.add_argument('--upload-mbps',type=float,default=20)
    p.add_argument('--dataset-gb',type=float,default=10);p.add_argument('--recipients',type=int,default=10000)
    p.add_argument('--host-upload-mbps',type=float,default=100)
    a=p.parse_args();print(json.dumps(estimate(**vars(a)),indent=2))
