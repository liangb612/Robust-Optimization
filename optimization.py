import gurobipy as gp
import numpy as np
import matplotlib.pyplot as plt
import model1
import model3
import model2

def main():
    modelm = gp.Model("robust")
    models = gp.Model("submodel")
    u_w_init = np.hstack((np.ones((1,12)),np.zeros((1,12))))
    u_v_init = np.hstack((np.ones((1,12)),np.zeros((1,12))))
    uin_init = {
        "uw":u_w_init,
        "uv":u_v_init
    }
   # print(f"u_w_init:{u_w_init}")
    #print(f"u_v_init:{u_v_init}")
    uout = model1.mainProblem_init(modelm,uin_init)
    pmin = model3.mainProblem_iterate_min(models,uout,uin_init)
    #print(f"pmin:{pmin}")
    uin = model2.mainProblem_iterate_max(models,uout,pmin)
    #print(f"UBin:{uin}")
    pmin = model3.mainProblem_iterate_min(models,uout,uin)
    while abs(pmin["LBin"]-uin["UBin"])>=200 :
        uin = model2.mainProblem_iterate_max(models,uout,pmin)
        pmin = model3.mainProblem_iterate_min(models,uout,uin)
    uout = model1.mainProblem_init(modelm,uin)
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
    for i, data in enumerate(tt):
        if (data[d] >= 0 for d in range(len(data))):
            plt.bar(
                range(len(data)), data, bottom=bottom, color=colors[i % len(colors)]
            )
            bottom += data

        if i == 6:
            plt.bar(range(len(data)), data, bottom=0, color=colors[i % len(colors)])
            plt.bar(
                range(len(data)), 0, bottom=bottom, color=colors[i % len(colors)]
            )
            # 设置图例和标签
    plt.legend(
        [
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
    )
    plt.ylim(-100, 1800)
    plt.xlabel("T")
    plt.ylabel("Power (MW)")
    plt.title("Contribution of the Source")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()
