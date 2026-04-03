import gurobipy as gp
import numpy as np
from gurobipy import GRB

def mainProblem_iterate_min(model1:gp.Model,uout:dict):
  #打印输入的值
  print(uout)
  '''
  已知参数
  '''
  alpha = 0.9
  w_l = np.array([0.9, 1, 1.1])
  pw_f = np.array(
    [188,237,188,181,204,156,174,186,118,
                    89,77,54,52,80,82,107,144,185,163,221,215,
                    240,223,190,]
                  ).reshape(1,24)
  pv_f = np.array(
          [0,0,0,0,0,2.2000,5.5000,17.0000,28.6000,32.0000,39.0000,42.6000,42.0000,
            41.6000,40.5000,41.2000,36.5000,28.0000,16.0000,6.6000,1.1000,0,
            0,0,]
                ).reshape(1,24)
  pload = np.array(
          [945,845,745,780,998,1095,1147,1199,1300,1397,1449,1498,1397,1297,
          1197,1048,1000,1100,1202,1375,1298,1101,900,800,]
                  )#双峰负荷曲线
  p_g_min = np.array([200, 200, 150, 120, 70])
  p_g_max = np.array([460, 400, 350, 300, 150])
  p_h_max = 280
  remp_u_d = np.array([240, 210, 150, 120, 70])  # >=pgmin
  t_on_and_off = np.array([8, 7, 6, 4, 3])
  a = 1e-5 * np.array([1.02, 1.21, 2.17, 3.42, 6.63])
  b = np.array([0.277, 0.288, 0.29, 0.292, 0.306])
  c = np.array([9.2, 8.8, 7.2, 5.2, 3.5])
  sit = np.array([25.6, 22.3, 16.2, 12.3, 4.6])
  e = np.array([0.877, 0.877, 0.877, 0.877, 0.979])
  lamda = np.array([0.94, 0.94, 0.94, 0.94, 1.03])
  # 储能模型中的常量
  capmax = 800
  p_s_max = 200
  p_s_min= 0
  socmax = 0.9#储能电量百分比
  socmin = 0.2 
  theta = 0.01
  yita = 0.95
  kees = 0.009
  # 碳交易
  w = 50
  d = 100
  tao = 0.25
  #碳排放因子
  #___________
  # 循环控制变量
  # 时间
  T = 24
  # 火力发电机组数
  n_g = 5

  '''
  约束规划
  '''
  #火电变量
  
  p_g = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name="火电出力")
  p_g_2 = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name = "火电出力的平方线性化")
  u_g = uout["ug"]
  u_start = uout["ustart"]
  u_stop = uout["ustop"]
  #火电约束
  #上下限约束，个数ng x T，爬坡约束，个数ng x T
  model1.addConstrs((p_g[i,j]<=u_g[i,j]*p_g_max[i] for i in range(n_g) for j in range(T)))
  model1.addConstrs((p_g[i,j]>=u_g[i,j]*p_g_min[i] for i in range(n_g) for j in range(T)))
  for i in range(n_g):
    for t in range(T):
      if(t==0):
        model1.addConstr(p_g[i,t]<=remp_u_d[i])#初值设为0
      else:  
        model1.addConstr(p_g[i,t]-p_g[i,t-1]<=remp_u_d[i])
        model1.addConstr(p_g[i,t-1]-p_g[i,t]<=remp_u_d[i])


  #火电成本
  #线性化二次项
  lxpg2=np.array([np.linspace(start =0,stop=p_g_max[i],num=11) for i in range(n_g)])
  lypg2 = lxpg2**2
  for n in range(n_g):
    for t in range(T):
      model1.addGenConstrPWL(p_g[n, t].item(), p_g_2[n, t].item(), lxpg2[n],lypg2[n])
  c_g = 0
  c_u = 0
  for i in range(n_g):
    for t in range(T):
      c_gi = a[i]*p_g_2[i,t]+ b[i]*p_g[i,t]+ c[i]
      c_u =c_u+ sit[i]*(u_start[i,t]+u_stop[i,t])
      c_g +=c_gi
  
  #水电：
  #变量：
  p_h = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name = "水电出力")
  # 约束：
  model1.addConstr(p_h<=p_h_max)
  # 成本：无
  
  #储能：
  soc_init = 0.5
  # 变量：
  soc = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = socmin,ub = socmax,name = "电量百分比")
  p_ch = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能充电功率")
  p_dis = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能放电功率")
  u_ch = uout["uch"]
  u_dis = uout["udis"]
#约束：
  model1.addConstr(p_ch<=p_s_max*u_ch)
  model1.addConstr(p_dis<=p_s_max*u_dis)
  model1.addConstr(soc[0,0] == soc_init*(1-theta)+p_ch[0,0]*yita/capmax-p_dis[0,0]/yita/capmax)
  for t in range(1,T):
    model1.addConstr(soc[0,t] == soc[0,t-1]*(1-theta)+p_ch[0,t]*yita/capmax-p_dis[0,t]/yita/capmax)
  model1.addConstr(soc[0,23]==soc_init)

  #成本：维护成本
  c_ees = kees*gp.quicksum(p_ch[0,t].item()*yita+p_dis[0,t].item()/yita for t in range(T))
  
  #风光电：
  F = 12#保守性调节常量
  d_p_w_max = 0.4#箱式边界系数
  d_p_v_max = 0.4
  #变量：
  p_w = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="风电出力")
  p_v = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="光电出力")
  u_w = model1.addMVar((1,T),vtype=GRB.BINARY,name="风电运行状态")
  u_v = model1.addMVar((1,T),vtype=GRB.BINARY,name="光电运行状态")
  #约束：
  model1.addConstr(gp.quicksum(u_w[0,t].item() for t in range(T))<=F)
  model1.addConstr(gp.quicksum(u_v[0,t].item() for t in range(T))<=F)
  model1.addConstr(p_w == pw_f-u_w*d_p_w_max*pw_f)#箱式边界的下界
  model1.addConstr(p_v == pv_f-u_v*d_p_v_max*pv_f)
  #成本:主要是弃风光惩罚
  c_wvt = 500*(pw_f-p_w)+500*(pv_f-p_v)
  c_wv=0
  for t in range(T):
    c_wv +=c_wvt[0,t]
  
  #负载模糊清晰化
  p_l_b = ((1 - alpha) * w_l[0] / 2+ w_l[1] / 2+ w_l[2] * alpha / 2) * pload
  print(f"plb:{p_l_b}")

  #电网：
  p_g_i=model1.addMVar((1, 24), lb=0,vtype=GRB.CONTINUOUS)
  pgmaxsum=model1.addMVar((1, 24),lb=0 ,vtype=GRB.CONTINUOUS)
  # 约束：
  
  for t in range(24):
      p_g_i_temp = gp.quicksum(p_g[n, t].item() for n in range(n_g))
      model1.addConstr(p_g_i[0,t]== p_g_i_temp)
  #model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-p_g_i==0)
  model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-p_g_i==0)
  
  for t in range(24):
      pgmaxsum_temp = gp.quicksum(u_g[n, t].item() * p_g_max[n] for n in range(n_g))
      model1.addConstr(pgmaxsum[0,t] == pgmaxsum_temp)
  #model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum<=0)
  model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum<=0)
#使用KKT条件转化为max：乘子始终对应“≤ 0”形式的约束，且非负。
#M取值
  M=10000
  #功率平衡约束对偶变量  
  dl_peq = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,name="功率平衡约束对偶变量")
  dl_prot = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="旋转备用约束对偶变量")
#火电对偶变量
  
  dl_p_g_max = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="功率上限对偶变量")
  dl_p_g_min = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="功率下限限对偶变量")
  dl_remp_g_max = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="爬坡约束对偶变量")
  dl_remp_g_min = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,lb=0,name="爬坡下限对偶变量")
  
  #水电约束对偶变量：
  dl_ph_max= model1.addMVar(shape = (1,T),vtype=GRB.CONTINUOUS,lb=0,name="水电上限对偶")
  dl_ph_min= model1.addMVar(shape = (1,T),vtype=GRB.CONTINUOUS,lb=0,name="水电下限对偶")
  
  #对偶可行性，不等式约束下限为零，等式约束不限制
  
  #互补松弛 对偶变量与原来的约束只有一个取到等号，不等式约束为取到等号的时候，其对偶变量必然不为0，
  #对偶变量为零时，约束必然不取等号，或者两个都取到等号
  #火电互补松弛：
  for i in range(n_g):
    for t in range(T):
      if t == 0:
        z0 = model1.addVar(vtype=GRB.BINARY)
        model1.addConstr(dl_remp_g_max[i,t] <= M * z0)
        model1.addConstr(p_g[i,t] - remp_u_d[i] >= -M * (1 - z0))
      else:
            # 原约束1：(p_g[i,t] - p_g[i,t-1] - ramp_up[i]) * dl_remp_g_max[i,t] == 0
        z1 = model1.addVar(vtype=GRB.BINARY)
        model1.addConstr(dl_remp_g_max[i,t] <= M * z1)
        model1.addConstr(p_g[i,t] - p_g[i,t-1] - remp_u_d[i] >= -M * (1 - z1))
            # 原约束2：(p_g[i,t-1] - p_g[i,t] - ramp_down[i]) * dl_remp_g_min[i,t] == 0
        z2 = model1.addVar(vtype=GRB.BINARY)
        model1.addConstr(dl_remp_g_min[i,t] <= M * z2)
        model1.addConstr(p_g[i,t-1] - p_g[i,t] - remp_u_d[i] >= -M * (1 - z2))
      z3 =model1.addVar(vtype=GRB.BINARY)
      model1.addConstr(dl_p_g_max[i,t] <= M * z3)
      model1.addConstr(p_g[i,t]-u_g[i,t]*p_g_max[i]>=-M*(1-z3))
      z4 =model1.addVar(vtype=GRB.BINARY)
      model1.addConstr(dl_p_g_min[i,t] <= M * z4)
      model1.addConstr(-p_g[i,t]+u_g[i,t]*p_g_min[i]>=-M*(1-z4))
  
  for t in range(T):    
  #水电互补松弛：
    z5 =model1.addVar(vtype=GRB.BINARY)
    model1.addConstr(dl_ph_max[0,t] <= M * z5)
    model1.addConstr(p_h[0,t]-p_h_max>=-M*(1-z5))
    z6=model1.addVar(vtype=GRB.BINARY)
    model1.addConstr(dl_ph_min[0,t] <= M * z6)
    model1.addConstr(-p_h[0,t]>=-M*(1-z6))
  
  #平稳性 拉格朗日函数为所有目标函数+对偶变量乘以约束，拉格朗日函数对原始优化变量的导数为0
  #火电平稳性：求出拉格朗日函数，对每个变量求偏导，结果相加等于0
  for i in range(n_g):
    for t in range(T):
      if t==0:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_remp_g_max[i,t+1]+dl_p_g_min[i,t+1]-dl_peq[0,t] 
      elif t==23:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_p_g_min[i,t]-dl_peq[0,t] 
      else:
        D_lagrange_p_g = a[i]*p_g[i,t]+b[i]+dl_p_g_max[i,t]-dl_p_g_min[i,t]+dl_remp_g_max[i,t]-dl_remp_g_max[i,t+1]-dl_remp_g_min[i,t]+dl_remp_g_min[i,t+1]-dl_peq[0,t]
      model1.addConstr(D_lagrange_p_g==0)  
  '''    
  #水电平稳性：
  model1.addConstr(dl_ph_max-dl_ph_min-dl_prot-dl_peq==0)
  '''
  
  #储能
  dl_p_ch_max   = model1.addMVar((1,T), lb=0,name="储能充电上限约束对偶")
  dl_p_dis_max  = model1.addMVar((1,T), lb=0,name="储能放电上限约束对偶")
  dl_soc       = model1.addMVar((1,T), vtype=GRB.CONTINUOUS,name="soc等式递推约束对偶")
  dl_soc_max  = model1.addMVar((1,T), lb=0,name="soc上限约束对偶")
  dl_soc_min  = model1.addMVar((1,T), lb=0,name="soc下限约束对偶")
  dl_p_ch_min  = model1.addMVar((1,T), lb=0,name="储能充电下限约束对偶")
  dl_p_dis_min = model1.addMVar((1,T), lb=0,name="储能放电下限约束对偶")
  dl_soc_blc       = model1.addVar(vtype=GRB.CONTINUOUS,name="储能放电平衡循环约束对偶")
  
  # ===================== 稳定性条件（全部线性！）=====================
  for t in range(T):
      # 对 p_ch 的稳定性：u_ch_val[0,t] 是已知常数
      model1.addConstr(kees * yita 
          + dl_p_ch_max[0,t] 
          -dl_soc[0,t] *  yita / capmax  # 线性！
          - dl_p_ch_min[0,t]+dl_peq[0,t]+dl_prot[0,t] == 0,
          name=f"stat_pch_{t}"
      )
      # 对 p_dis 的稳定性：u_dis_val[0,t] 是已知常数
      model1.addConstr(
          kees / yita 
          + dl_p_dis_max[0,t] 
          + dl_soc[0,t] / yita /capmax # 线性！
          - dl_p_dis_min[0,t]-dl_peq[0,t]-dl_prot[0,t] == 0,
          name=f"stat_pdis_{t}"
      )
  "!!!!!!!!!!!!!!!!!!!!!下面的储能稳定性约束是问题的来源!!!!!!!!!!!!!!!!!!!!!!"
  
  # 对 soc_t 的稳定性（t < T-1）
  for t in range(1,T-1):
      model1.addConstr(
          dl_soc[0,t-1] 
          - dl_soc[0,t] * (1 - theta) 
          + dl_soc_max[0,t] 
          - dl_soc_min[0,t] == 0,
          name=f"stat_soc_{t}"
      )
  
  # 对 soc_{T-1} 的平稳性
  model1.addConstr(
      dl_soc[0,T-1] 
      + dl_soc_blc == 0,
      name="stat_soc_T"
  )
  
  "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  # ===================== 互补松弛条件（Big-M线性化）=====================
  z_lch  = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_lch")
  z_ldis = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_ldis")
  z_au   = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_au")
  z_al   = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_al")
  z_bch  = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_bch")
  z_bdis = model1.addMVar((1,T), vtype=GRB.BINARY, name="z_bdis")
  for t in range(T):
    # --- λ_ch * (p_ch - p_s_max * u_ch) = 0 ---
    model1.addConstr(dl_p_ch_max[0,t] <= M * z_lch[0,t])
    model1.addConstr(p_ch[0,t] - p_s_max * u_ch[0,t] >= -M * (1 - z_lch[0,t]))
    model1.addConstr(p_ch[0,t] - p_s_max * u_ch[0,t] <=  M * (1 - z_lch[0,t]))
    # --- λ_dis * (p_dis - p_s_max * u_dis) = 0 ---
    model1.addConstr(dl_p_dis_max[0,t] <= M * z_ldis[0,t])
    model1.addConstr(p_dis[0,t] - p_s_max * u_dis[0,t] >= -M * (1 - z_ldis[0,t]))
    model1.addConstr(p_dis[0,t] - p_s_max * u_dis[0,t] <=  M * (1 - z_ldis[0,t]))
    # --- α_u * (soc - soc_max) = 0 ---
    model1.addConstr(dl_soc_max[0,t] <= M * z_au[0,t])
    model1.addConstr(soc[0,t] - socmax >= -M * (1 - z_au[0,t]))
    model1.addConstr(soc[0,t] - socmax <=  M * (1 - z_au[0,t]))
    # --- α_l * (soc - soc_min) = 0 ---
    model1.addConstr(dl_soc_min[0,t] <= M * z_al[0,t])
    model1.addConstr(soc[0,t] - socmin >= -M * (1 - z_al[0,t]))
    model1.addConstr(soc[0,t] - socmin <=  M * (1 - z_al[0,t]))
    # --- β_ch * p_ch = 0 ---
    model1.addConstr(dl_p_ch_min[0,t] <= M * z_bch[0,t])
    model1.addConstr(p_ch[0,t]  <= M * (1 - z_bch[0,t]))
    # --- β_dis * p_dis = 0 ---
    model1.addConstr(dl_p_dis_min[0,t] <= M * z_bdis[0,t])
    model1.addConstr(p_dis[0,t]<= M * (1 - z_bdis[0,t]))
  
  #电网KKT：
  #model1.addConstr((p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum)*dl_prot==0)
  z_net = model1.addMVar((1,T), vtype=GRB.BINARY)
  for t in range(T):
    model1.addConstr(dl_prot[0,t] <= M * z_net[0,t])
    model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-pgmaxsum>= -M * (1 - z_net[0,t]))

  #目标函数加入KKT条件后失效，直接并入外层的max 
  '''
  ------------------------------------------------------------------
  '''
  C = model1.addVar(vtype=GRB.CONTINUOUS,name="子问题最恶劣场景下的成本")
  model1.addConstr( C <= c_ees+c_g+c_wv)
  '''
  -------------------------------------------------------------------
  '''
  #model1.Params.NonConvex = 2
  model1.setParam(GRB.Param.OptimalityTol, 1e-8)
  model1.setParam(GRB.Param.FeasibilityTol, 1e-8)  
  model1.setObjective(C+c_u, GRB.MAXIMIZE)
  model1.optimize()
  if model1.status != GRB.OPTIMAL:
      print("Model is infeasible. Computing IIS...")
      model1.computeIIS()
      model1.write("infeasible.ilp")
      print("IIS written to 'infeasible.ilp'")
  elif model1.status == GRB.UNBOUNDED:
      print("IIS written to 'infeasible.ilp un'")
  else:
    UBin = model1.ObjVal
    P_G = p_g.X
    P_H = p_h.X
    P_W = p_w.X
    P_CH = p_ch.X
    P_DIS = p_dis.X
    P_V = p_v.X
    soc = soc.X
    U_V=u_v.X
    U_W =u_w.X 
    rst = {
      "p_g": P_G,
      "P_H": P_H,
      "p_ch": P_CH,
      "p_dis": P_DIS,
      "soc": soc,
      "p_w": P_W,
      "P_V": P_V,
      "UBin": UBin,

      "uv":U_V,
      "uw":U_W
    }

    return(rst)
