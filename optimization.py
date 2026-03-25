from scipy.ndimage import label
from matplotlib.legend import Legend
from scipy.constants import h
import gurobipy as gp
import numpy as np
import matplotlib.pyplot as plt
import model1
import model3


def main():
    modelm = gp.Model("robust")
    models = gp.Model("submodel")
    u_w_init = np.hstack((np.zeros((1,12)),np.ones((1,12))))
    u_v_init = np.hstack((np.zeros((1,12)),np.ones((1,12))))
    uin_init = {
        "uw":u_w_init,
        "uv":u_v_init
    }
   # print(f"u_w_init:{u_w_init}")
    #print(f"u_v_init:{u_v_init}")
    uout = model1.mainProblem_init(modelm,uin_init)
    uin = model3.mainProblem_iterate_min(models,uout)
    print(f"内层kkt条件的优化结果:\n{uin}")
    #print(f"UBin:{uin}")
    while abs(uout["LB"]-uin["UBin"])>=2000 :
        uout = model1.mainProblem_init(modelm,uin)
        uin = model3.mainProblem_iterate_min(models,uout)
    print("_______________________________________________________________")
    print(uout)
    tt = np.vstack(
        [
            uout["p_g"][0,:],  
            uout["p_g"][1,:],  
            uout["p_g"][2,:],  
            uout["p_g"][3,:],  
            uout["p_g"][4,:],  
            uout["p_h"],
            -uout["p_ch"],
            uout["p_dis"],
            uout["p_w"],
            uout["p_v"],
        ]
    )
    

    # 创建堆叠柱状图
    plt.figure(figsize=(12, 6))
    bottom = np.zeros(len(tt[0]))  # 初始化底部位置
    colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9364c0",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]
     # 设置图例和标签
    legends=[
            "thermal generator1",
            "thermal generator2",
            "thermal generator3",
            "thermal generator4",
            "thermal generator5",
            "hydropower generator",
            "ESS charge",
            "ESS discharge",
            "wind power",
            "photovoltaic",
        ]
    for i, data in enumerate(tt):
        if (data>=0).all():
            plt.bar(
                x=range(len(data)), 
                height=data, 
                bottom=bottom, 
                color=colors[i % len(colors)],
                label=legends[i%len(legends)]
            )
            bottom += data

        if (data<=0).all():
            plt.bar(
            x=range(len(data)), 
            height=data, 
            bottom=0, 
            color=colors[i % len(colors)],
            label=legends[i%len(legends)]
            )

    plt.legend()
    plt.ylim(-100, 1800)
    plt.xlabel("T")
    plt.ylabel("Power (MW)")
    plt.title("Contribution of the Source")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
